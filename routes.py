import os
import time
from flask import Blueprint, render_template, request, jsonify, send_from_directory, current_app, send_file, abort
from werkzeug.utils import secure_filename
from models import db, Subsection, Media, Home, HomeMedia, Button, ButtonMedia
from constants import SECTIONS, get_section_by_id
from helpers import send_to_s3, delete_from_s3
import requests

# Create blueprint
bp = Blueprint('sections', __name__)

def allowed_file(filename):
    allowed = '.' in filename and filename.rsplit('.', 1)[1].lower() in current_app.config['ALLOWED_EXTENSIONS']
    if not allowed:
        print(f"File extension not allowed: {filename.rsplit('.', 1)[1].lower() if '.' in filename else 'no extension'}")
    return allowed

# Page Routes
@bp.route('/manage-sections')
def manage_sections():
    subsections = Subsection.query.all()
    # Add section info to subsections
    subsections_with_sections = []
    for subsection in subsections:
        section = get_section_by_id(subsection.section_id)
        if section:
            subsection_dict = {
                'id': subsection.id,
                'name': subsection.name,
                'description': subsection.description,
                'section_id': subsection.section_id,
                'section_name': section['name'],
                'media_count': len(subsection.media_items)
            }
            subsections_with_sections.append(subsection_dict)
    
    return render_template('manage_sections.html', 
                         sections=SECTIONS,
                         subsections=subsections_with_sections)

# API Routes - Remove section-related routes since they're now constants
@bp.route('/api/subsections', methods=['GET'])
def get_subsections():
    subsections = Subsection.query.all()
    return jsonify([{
        'id': s.id,
        'section_id': s.section_id,
        'section_name': get_section_by_id(s.section_id)['name'],
        'name': s.name,
        'description': s.description
    } for s in subsections])

@bp.route('/api/subsections/<int:id>', methods=['GET'])
def get_subsection(id):
    subsection = Subsection.query.get_or_404(id)
    section = get_section_by_id(subsection.section_id)
    return jsonify({
        'id': subsection.id,
        'section_id': subsection.section_id,
        'section_name': section['name'] if section else None,
        'name': subsection.name,
        'description': subsection.description
    })

@bp.route('/api/subsections', methods=['POST'])
def create_subsection():
    data = request.form
    section_id = data.get('section_id')
    name = data.get('name')
    description = data.get('description')
    
    if not all([section_id, name]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    subsection = Subsection(
        section_id=section_id,
        name=name,
        description=description
    )
    
    db.session.add(subsection)
    db.session.commit()
    
    return jsonify({
        'id': subsection.id,
        'name': subsection.name,
        'description': subsection.description
    })

@bp.route('/api/subsections/<int:id>', methods=['PUT'])
def update_subsection(id):
    subsection = Subsection.query.get_or_404(id)
    data = request.json
    
    # Validate that section_id exists in SECTIONS
    if not get_section_by_id(int(data['section_id'])):
        return jsonify({'error': 'Invalid section ID'}), 400
        
    subsection.section_id = data['section_id']
    subsection.name = data['name']
    subsection.description = data.get('description', subsection.description)
    db.session.commit()
    return jsonify({'success': True})

@bp.route('/api/subsections/<int:id>', methods=['DELETE'])
def delete_subsection(id):
    subsection = Subsection.query.get_or_404(id)
    db.session.delete(subsection)
    db.session.commit()
    return '', 204

# Media Routes
@bp.route('/api/subsections/<int:id>/media', methods=['GET'])
def get_subsection_media(id):
    media_items = Media.query.filter_by(subsection_id=id).all()
    return jsonify([{
        'id': m.id,
        'type': m.type,
        'file_path': m.file_path,
        'title': m.title,
        'description': m.description
    } for m in media_items])

@bp.route('/api/media', methods=['POST'])
def upload_media():
    if 'file' not in request.files:
        return jsonify({'error': 'No file provided'}), 400
        
    file = request.files['file']
    subsection_id = request.form.get('subsection_id')
    media_type = request.form.get('type')
    title = request.form.get('title')
    description = request.form.get('description')
    
    if not all([file, subsection_id, media_type, title]):
        return jsonify({'error': 'Missing required fields'}), 400
        
    # Generate unique filename
    filename = secure_filename(file.filename)
    unique_filename = f"{subsection_id}_{int(time.time())}_{filename}"
    
    # Upload to S3
    bucket_name = current_app.config['S3_BUCKET']
    result = send_to_s3(file, bucket_name, unique_filename)
    
    if result != 'success':
        return jsonify({'error': f'Failed to upload to S3: {result}'}), 500
    
    # Create S3 URL - Remove any trailing slash from S3_LOCATION
    s3_location = current_app.config['S3_LOCATION'].rstrip('/')
    s3_url = f"{s3_location}/{unique_filename}"
    
    # Create media record
    media = Media(
        subsection_id=subsection_id,
        type=media_type,
        title=title,
        description=description,
        file_path=s3_url
    )
    
    try:
        db.session.add(media)
        db.session.commit()
        
        return jsonify({
            'id': media.id,
            'type': media.type,
            'title': media.title,
            'description': media.description,
            'file_path': media.file_path
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/media/<int:media_id>', methods=['DELETE'])
def delete_media(media_id):
    media = Media.query.get_or_404(media_id)
    
    # Delete file from S3
    result = delete_from_s3(media.file_path)
    if result != 'success':
        return jsonify({'error': f'Failed to delete from S3: {result}'}), 500
    
    # Delete record from database
    try:
        db.session.delete(media)
        db.session.commit()
        return jsonify({'message': 'Media deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/media/update-title', methods=['PUT'])
def update_media_title():
    data = request.json
    if not data or 'original_title' not in data or 'new_title' not in data:
        return jsonify({'error': 'Missing required fields'}), 400
    
    try:
        # Update all media items with the same title
        Media.query.filter_by(title=data['original_title']).update({
            'title': data['new_title'],
            'description': data.get('description', '')
        })
        db.session.commit()
        return jsonify({'message': 'Media updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/media/batch', methods=['POST'])
def upload_media_batch():
    if 'files[]' not in request.files:
        return jsonify({'error': 'No files provided'}), 400
        
    files = request.files.getlist('files[]')
    subsection_id = request.form.get('subsection_id')
    title = request.form.get('title')
    description = request.form.get('description', '')
    
    if not all([files, subsection_id, title]):
        return jsonify({'error': 'Missing required fields'}), 400

    uploaded_media = []
    bucket_name = current_app.config['S3_BUCKET']
    
    for file in files:
        if file and allowed_file(file.filename):
            try:
                # Generate unique filename
                filename = secure_filename(file.filename)
                unique_filename = f"{subsection_id}_{int(time.time())}_{filename}"
                
                # Determine media type from file extension
                file_ext = filename.rsplit('.', 1)[1].lower()
                if file_ext in ['jpg', 'jpeg', 'png', 'gif']:
                    media_type = 'image'
                elif file_ext in ['mp4', 'mkv', 'mov']:
                    media_type = 'video'
                elif file_ext == 'pdf':
                    media_type = 'pdf'
                else:
                    continue  # Skip unsupported file types
                
                # Upload to S3
                result = send_to_s3(file, bucket_name, unique_filename)
                
                if result != 'success':
                    raise Exception(f"Failed to upload to S3: {result}")
                
                # Create S3 URL - Remove any trailing slash from S3_LOCATION
                s3_location = current_app.config['S3_LOCATION'].rstrip('/')
                s3_url = f"{s3_location}/{unique_filename}"
                
                # Create media record with the same title and description for all files
                media = Media(
                    subsection_id=subsection_id,
                    type=media_type,
                    title=title,
                    description=description,
                    file_path=s3_url
                )
                
                db.session.add(media)
                uploaded_media.append({
                    'type': media_type,
                    'title': title,
                    'description': description,
                    'file_path': s3_url
                })
            except Exception as e:
                print(f"Error uploading file {filename}: {str(e)}")
                continue
    
    if not uploaded_media:
        return jsonify({'error': 'No files were successfully uploaded'}), 400
    
    try:
        db.session.commit()
        # Update the IDs after commit
        for media_item in uploaded_media:
            media_record = Media.query.filter_by(
                subsection_id=subsection_id,
                title=media_item['title']
            ).first()
            if media_record:
                media_item['id'] = media_record.id
                
        return jsonify({
            'message': f'Successfully uploaded {len(uploaded_media)} files',
            'media': uploaded_media
        })
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Serve uploaded files
@bp.route('/uploads/<path:filename>')
def uploaded_file(filename):
    return send_from_directory(current_app.config['UPLOAD_FOLDER'], filename)

@bp.route('/sections/<int:section_id>/subsections')
def view_section_subsections(section_id):
    # Get section info
    section = get_section_by_id(section_id)
    if not section:
        return render_template('error.html', message='Section not found'), 404
        
    # Get subsections for this section
    subsections = Subsection.query.filter_by(section_id=section_id).all()
    
    # Add media counts to subsections
    subsections_with_media = []
    for subsection in subsections:
        media_by_type = {
            'image': 0,
            'video': 0,
            'pdf': 0
        }
        for media in subsection.media_items:
            if media.type in media_by_type:
                media_by_type[media.type] += 1
                
        subsection_data = {
            'id': subsection.id,
            'name': subsection.name,
            'description': subsection.description,
            'media_counts': media_by_type,
            'total_media': len(subsection.media_items)
        }
        subsections_with_media.append(subsection_data)
    
    return render_template('view_section.html', 
                         section=section,
                         subsections=subsections_with_media)

@bp.route('/subsections/<int:id>/view')
def view_subsection(id):
    # Get subsection details
    subsection = Subsection.query.get_or_404(id)
    section = get_section_by_id(subsection.section_id)
    
    # Group media by type
    media_by_type = {
        'image': [],
        'video': [],
        'pdf': []
    }
    for media in subsection.media_items:
        if media.type in media_by_type:
            media_by_type[media.type].append({
                'id': media.id,
                'file_path': media.file_path,
                'title': media.title,
                'description': media.description
            })
    
    return render_template('view_subsection.html',
                         subsection=subsection,
                         section=section,
                         media_by_type=media_by_type)

@bp.route('/sections/<int:section_id>/manage-subsections')
def manage_subsections(section_id):
    # Get section info
    section = get_section_by_id(section_id)
    if not section:
        return render_template('error.html', message='Section not found'), 404
        
    # Get subsections for this section
    subsections = Subsection.query.filter_by(section_id=section_id).all()
    
    # Add media counts to subsections
    subsections_with_media = []
    for subsection in subsections:
        media_by_type = {
            'image': 0,
            'video': 0,
            'pdf': 0
        }
        for media in subsection.media_items:
            if media.type in media_by_type:
                media_by_type[media.type] += 1
                
        subsection_data = {
            'id': subsection.id,
            'name': subsection.name,
            'description': subsection.description,
            'media_counts': media_by_type,
            'total_media': len(subsection.media_items)
        }
        subsections_with_media.append(subsection_data)
    
    return render_template('manage_subsections.html', 
                         section=section,
                         subsections=subsections_with_media)

def group_media_by_title(media_items):
    """Helper function to group media items by title"""
    grouped = {}
    for media in media_items:
        # Convert media item to dictionary
        media_dict = {
            'id': media.id,
            'type': media.type,
            'file_path': media.file_path,
            'title': media.title,
            'description': media.description
        }
        
        if media.title in grouped:
            grouped[media.title]['items'].append(media_dict)
            grouped[media.title]['count'] += 1
        else:
            grouped[media.title] = {
                'description': media.description,
                'items': [media_dict],
                'count': 1
            }
    return grouped

@bp.route('/subsections/<int:subsection_id>/manage-media')
def manage_media(subsection_id):
    subsection = Subsection.query.get_or_404(subsection_id)
    media_items = Media.query.filter_by(subsection_id=subsection_id).all()
    
    # Create a simple list of dictionaries for the template
    media_list = []
    for media in media_items:
        media_list.append({
            'id': media.id,
            'type': media.type,
            'file_path': media.file_path,
            'title': media.title,
            'description': media.description or ''
        })
    
    return render_template('manage_media.html', 
                         subsection=subsection,
                         media_items=media_list)

@bp.route('/api/media/map-toggle', methods=['POST'])
def map_toggle_media():
    """
    Map or unmap media to a kiosk button based on subsection name.
    
    Request body:
    {
        "title": "Media title",
        "subsection_name": "Subsection name",
        "action": "map" or "unmap"
    }
    """
    try:
        data = request.json
        
        if not data:
            return jsonify({"error": "No data provided"}), 400
            
        # Required fields
        title = data.get('title')
        subsection_name = data.get('subsection_name')
        action = data.get('action')
        
        if not all([title, subsection_name, action]):
            return jsonify({"error": "Missing required fields: title, subsection_name, or action"}), 400
            
        if action not in ['map', 'unmap']:
            return jsonify({"error": "Action must be 'map' or 'unmap'"}), 400
        
        # 1. Get media items by title
        media_items = Media.query.filter_by(title=title).all()
        
        if not media_items:
            return jsonify({"error": f"No media found with title '{title}'"}), 404
            
        # 2. Get button id from button table by subsection name (case insensitive)
        button = Button.query.filter(db.func.lower(Button.title) == db.func.lower(subsection_name)).first()
        
        if not button:
            return jsonify({"error": f"No button found with title matching '{subsection_name}'"}), 404
        
        if action == 'map':
            # 3. Insert new ButtonMedia records with data from Media
            inserted_count = 0
            for media in media_items:
                # Create new ButtonMedia record with data copied from Media
                new_button_media = ButtonMedia(
                    button_id=button.id,
                    type=media.type,
                    file_path=media.file_path,
                    title=media.title,
                    description=media.description
                )
                db.session.add(new_button_media)
                inserted_count += 1
            
            db.session.commit()
            return jsonify({
                "message": f"Successfully copied {inserted_count} media items to button",
                "button_id": button.id
            }), 200
            
        else:  # action == 'unmap'
            # For unmapping, delete ButtonMedia entries with matching button_id and Media properties
            deleted_count = 0
            for media in media_items:
                # Find and delete ButtonMedia entries that match this button and have same properties as media
                button_media = ButtonMedia.query.filter_by(
                    button_id=button.id,
                    title=media.title
                ).all()
                
                for item in button_media:
                    db.session.delete(item)
                    deleted_count += 1
            
            db.session.commit()
            return jsonify({
                "message": f"Successfully removed {deleted_count} media items from button"
            }), 200
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in map_toggle_media: {str(e)}")
        return jsonify({"error": str(e)}), 500

MEDIA_DIR = './uploads'

UPLOADS_DIR = os.path.join(os.getcwd(), 'uploads')


@bp.route("/media/<path:filename>")
def serve_media(filename):

    S3_BASE_URL = current_app.config['S3_LOCATION'].rstrip('/')
    local_path = os.path.join(UPLOADS_DIR, filename)

    if os.path.exists(local_path):
        return send_file(local_path)

    # Download from S3
    s3_url = f"{S3_BASE_URL}/{filename}"
    response = requests.get(s3_url)

    if response.status_code != 200:
        abort(404, description="File not found on S3")

    # Make sure the uploads directory exists
    os.makedirs(UPLOADS_DIR, exist_ok=True)

    # Save the file
    with open(local_path, "wb") as f:
        f.write(response.content)

    return send_file(local_path)