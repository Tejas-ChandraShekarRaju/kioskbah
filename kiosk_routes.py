from flask import Blueprint, render_template, request, jsonify, current_app
from models import db, Kiosk, Video, Button, ButtonMedia, Home
from datetime import datetime
from werkzeug.utils import secure_filename
import os
import time
from helpers import send_to_s3, delete_from_s3

bp = Blueprint('kiosks', __name__)

@bp.route('/manage-kiosks')
def manage_kiosks():
    """Render the kiosk management page"""
    kiosks = Kiosk.query.order_by(Kiosk.created_at.desc()).all()
    return render_template('manage_kiosks.html', kiosks=kiosks)

@bp.route('/kiosks/<int:kiosk_id>/manage-videos')
def manage_videos(kiosk_id):
    """Render the video management page for a specific kiosk"""
    kiosk = Kiosk.query.get_or_404(kiosk_id)
    videos = Video.query.filter_by(kiosk_id=kiosk_id).order_by(Video.created_at.desc()).all()
    return render_template('manage_videos.html', kiosk=kiosk, videos=videos)

@bp.route('/api/kiosks', methods=['POST'])
def create_kiosk():
    """Create a new kiosk"""
    data = request.get_json()
    
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
        
    kiosk = Kiosk(
        title=data['title'],
        description=data.get('description', '')
    )
    
    try:
        db.session.add(kiosk)
        db.session.commit()
        return jsonify({'message': 'Kiosk created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/videos', methods=['POST'])
def upload_video():
    """Upload a new video"""
    if 'video' not in request.files:
        return jsonify({'error': 'No video file provided'}), 400
        
    video_file = request.files['video']
    if video_file.filename == '':
        return jsonify({'error': 'No video selected'}), 400
        
    if not video_file.filename.lower().endswith(('.mp4', '.webm', '.ogg')):
        return jsonify({'error': 'Invalid video format. Please upload MP4, WebM, or OGG files.'}), 400

    try:
        # Generate unique filename with timestamp
        filename = secure_filename(video_file.filename)
        kiosk_id = request.form.get('kiosk_id')
        unique_filename = f"videos/{kiosk_id}_{int(time.time())}_{filename}"
        
        # Upload to S3
        bucket_name = current_app.config['S3_BUCKET']
        result = send_to_s3(video_file, bucket_name, unique_filename)
        
        if result != 'success':
            return jsonify({'error': f'Failed to upload to S3: {result}'}), 500
        
        # Create S3 URL
        s3_location = current_app.config['S3_LOCATION'].rstrip('/')
        file_path = f"{s3_location}/{unique_filename}"
        
        # Create video record
        video = Video(
            kiosk_id=request.form.get('kiosk_id', type=int),
            title=request.form.get('title', ''),
            description=request.form.get('description', ''),
            file_path=file_path
        )
        
        db.session.add(video)
        db.session.commit()
        
        return jsonify({
            'message': 'Video uploaded successfully',
            'video': {
                'id': video.id,
                'title': video.title,
                'file_path': video.file_path
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/videos/<int:video_id>', methods=['DELETE'])
def delete_video(video_id):
    """Delete a video"""
    video = Video.query.get_or_404(video_id)
    
    try:
        # Delete from S3
        result = delete_from_s3(video.file_path)
        if result != 'success':
            return jsonify({'error': f'Failed to delete from S3: {result}'}), 500
            
        db.session.delete(video)
        db.session.commit()
        return jsonify({'message': 'Video deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/videos/<int:video_id>', methods=['PUT'])
def update_video(video_id):
    """Update an existing video's metadata"""
    video = Video.query.get_or_404(video_id)
    data = request.get_json()
    
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
        
    try:
        video.title = data['title']
        video.description = data.get('description', video.description)
        video.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'message': 'Video updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/kiosks/<int:kiosk_id>', methods=['PUT'])
def update_kiosk(kiosk_id):
    """Update an existing kiosk"""
    kiosk = Kiosk.query.get_or_404(kiosk_id)
    data = request.get_json()
    
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
        
    try:
        kiosk.title = data['title']
        kiosk.description = data.get('description', kiosk.description)
        kiosk.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'message': 'Kiosk updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/kiosks/<int:kiosk_id>', methods=['DELETE'])
def delete_kiosk(kiosk_id):
    """Delete a kiosk and all its associated videos and buttons"""
    kiosk = Kiosk.query.get_or_404(kiosk_id)
    
    try:
        # Delete associated video files
        for video in kiosk.videos:
            file_path = os.path.join(current_app.root_path, 'static', video.file_path)
            if os.path.exists(file_path):
                os.remove(file_path)
        
        db.session.delete(kiosk)
        db.session.commit()
        return jsonify({'message': 'Kiosk deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/videos/<int:video_id>/preview', methods=['GET'])
def preview_video(video_id):
    """Get video details for preview"""
    video = Video.query.get_or_404(video_id)
    return jsonify({
        'id': video.id,
        'title': video.title,
        'description': video.description,
        'file_path': video.file_path
    })

@bp.route('/videos/<int:video_id>/manage-buttons')
def manage_buttons(video_id):
    """Render the button management page for a specific video"""
    video = Video.query.get_or_404(video_id)
    buttons = Button.query.filter_by(video_id=video_id).all()
    return render_template('manage_buttons.html', video=video, buttons=buttons)

@bp.route('/api/buttons', methods=['POST'])
def create_button():
    """Create a new button"""
    data = request.form
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    try:
        button = Button(
            video_id=data['video_id'],
            title=data['title']
        )
        db.session.add(button)
        db.session.commit()
        return jsonify({'message': 'Button created successfully'}), 201
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/buttons/<int:button_id>', methods=['DELETE'])
def delete_button(button_id):
    """Delete a button"""
    button = Button.query.get_or_404(button_id)
    try:
        db.session.delete(button)
        db.session.commit()
        return jsonify({'message': 'Button deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/buttons/<int:button_id>', methods=['PUT'])
def update_button(button_id):
    """Update a button"""
    button = Button.query.get_or_404(button_id)
    data = request.json

    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400

    try:
        button.title = data['title']
        db.session.commit()
        return jsonify({'message': 'Button updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/buttons/<int:button_id>/manage-media')
def manage_button_media(button_id):
    """Render the media management page for a specific button"""
    button = Button.query.get_or_404(button_id)
    media_items = ButtonMedia.query.filter_by(button_id=button_id).order_by(ButtonMedia.created_at.desc()).all()
    
    # Convert button to dictionary
    button_dict = {
        'id': button.id,
        'title': button.title,
        'video_id': button.video_id
    }
    
    # Convert media items to dictionaries
    media_list = []
    for media in media_items:
        media_list.append({
            'id': media.id,
            'type': media.type,
            'file_path': media.file_path,
            'title': media.title,
            'description': media.description or ''
        })
    
    return render_template('manage_button_media.html', button=button_dict, media_items=media_list)

def determine_file_type(filename):
    """Determine media type based on file extension"""
    ext = filename.rsplit('.', 1)[1].lower() if '.' in filename else ''
    if ext in ['jpg', 'jpeg', 'png', 'gif']:
        return 'image'
    elif ext in ['mp4', 'mkv', 'mov']:
        return 'video'
    elif ext == 'pdf':
        return 'pdf'
    return 'other'

@bp.route('/api/button-media', methods=['POST'])
def upload_button_media():
    """Upload new media for a button"""
    if 'media' not in request.files:
        return jsonify({'error': 'No media file provided'}), 400
        
    media_file = request.files['media']
    if media_file.filename == '':
        return jsonify({'error': 'No file selected'}), 400

    allowed_extensions = {
        'image': ['.jpg', '.jpeg', '.png', '.gif'],
        'video': ['.mp4', '.webm', '.ogg']
    }
    
    file_ext = os.path.splitext(media_file.filename)[1].lower()
    media_type = request.form.get('type', 'image')
    
    if file_ext not in allowed_extensions.get(media_type, []):
        return jsonify({'error': f'Invalid file format for {media_type}'}), 400

    try:
        button_id = request.form.get('button_id')
        title = request.form.get('title')
        description = request.form.get('description')
        
        if not all([button_id, title]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Generate unique filename
        filename = secure_filename(media_file.filename)
        unique_filename = f"uploads/buttons/{button_id}_{int(time.time())}_{filename}"
        
        # Upload to S3
        bucket_name = current_app.config['S3_BUCKET']
        s3_location = current_app.config['S3_LOCATION'].rstrip('/')
        result = send_to_s3(media_file, bucket_name, unique_filename)
        
        if result != 'success':
            return jsonify({'error': f'Failed to upload to S3: {result}'}), 500
        
        # Create media record
        media = ButtonMedia(
            button_id=button_id,
            type=media_type,
            title=title,
            description=description,
            file_path=f"{s3_location}/{unique_filename}"
        )
        
        db.session.add(media)
        db.session.commit()
        
        return jsonify({
            'message': 'Media uploaded successfully',
            'media': {
                'id': media.id,
                'type': media_type,
                'title': title,
                'file_path': f"{s3_location}/{unique_filename}"
            }
        }), 201
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/button-media/batch', methods=['POST'])
def upload_button_media_batch():
    """Upload multiple media files for a button"""
    try:
        # Debug logging
        print("Request Files:", request.files)
        print("Request Form Data:", request.form)
        
        if 'files[]' not in request.files:
            print("Missing files[] in request.files")
            return jsonify({'error': 'No files provided'}), 400
            
        files = request.files.getlist('files[]')
        button_id = request.form.get('button_id')
        title = request.form.get('title')
        description = request.form.get('description')
        
        # Debug logging
        print(f"Files count: {len(files)}")
        print(f"Button ID: {button_id}")
        print(f"Title: {title}")
        print(f"Description: {description}")
        
        # Check S3 configuration
        bucket_name = current_app.config.get('S3_BUCKET')
        s3_location = current_app.config.get('S3_LOCATION')
        
        if not bucket_name or not s3_location:
            print("Missing S3 configuration")
            print(f"S3_BUCKET: {bucket_name}")
            print(f"S3_LOCATION: {s3_location}")
            return jsonify({'error': 'S3 configuration missing'}), 500
            
        # Validate required fields
        missing_fields = []
        if not files:
            missing_fields.append('files')
        if not button_id:
            missing_fields.append('button_id')
        if not title:
            missing_fields.append('title')
            
        if missing_fields:
            error_msg = f"Missing required fields: {', '.join(missing_fields)}"
            print(error_msg)
            return jsonify({'error': error_msg}), 400

        uploaded_media = []
        s3_location = s3_location.rstrip('/')
        
        # Track processed files to avoid duplicates
        processed_files = set()
        
        for file in files:
            if not file or not file.filename:
                print(f"Skipping empty file or filename")
                continue
                
            # Skip if we've already processed this file
            if file.filename in processed_files:
                print(f"Skipping duplicate file: {file.filename}")
                continue
                
            file_ext = os.path.splitext(file.filename)[1].lower()
            if file_ext not in ['.jpg', '.jpeg', '.png', '.gif', '.mp4', '.webm', '.ogg']:
                print(f"Skipping file with unsupported extension: {file_ext}")
                continue
                
            try:
                # Generate unique filename
                filename = secure_filename(file.filename)
                timestamp = int(time.time() * 1000)  # Use milliseconds for better uniqueness
                unique_filename = f"uploads/buttons/{button_id}_{timestamp}_{filename}"
                print(f"Processing file: {filename} -> {unique_filename}")
                
                # Determine media type
                media_type = 'image' if file_ext in ['.jpg', '.jpeg', '.png', '.gif'] else 'video'
                
                # Upload to S3
                result = send_to_s3(file, bucket_name, unique_filename)
                print(f"S3 upload result for {filename}: {result}")
                
                if result != 'success':
                    print(f"S3 upload failed for {filename}: {result}")
                    continue
                
                # Create media record
                media = ButtonMedia(
                    button_id=button_id,
                    type=media_type,
                    title=title,
                    description=description,
                    file_path=f"{s3_location}/{unique_filename}"
                )
                
                db.session.add(media)
                uploaded_media.append({
                    'type': media_type,
                    'title': title,
                    'file_path': f"{s3_location}/{unique_filename}"
                })
                print(f"Added media record for {filename}")
                
                # Mark file as processed
                processed_files.add(file.filename)
                
            except Exception as e:
                print(f"Error processing file {filename}: {str(e)}")
                continue
        
        if not uploaded_media:
            print("No files were successfully uploaded")
            return jsonify({'error': 'No files were successfully uploaded'}), 400
        
        try:
            print(f"Committing {len(uploaded_media)} media records to database")
            db.session.commit()
            return jsonify({
                'message': f'Successfully uploaded {len(uploaded_media)} files',
                'media': uploaded_media
            })
        except Exception as e:
            print(f"Database commit error: {str(e)}")
            db.session.rollback()
            return jsonify({'error': 'Failed to save media records to database'}), 500
            
    except Exception as e:
        print(f"Unexpected error in upload_button_media_batch: {str(e)}")
        return jsonify({'error': 'An unexpected error occurred'}), 500

@bp.route('/api/button-media/update-title', methods=['PUT'])
def update_button_media_title():
    """Update title for all button media items with the same title"""
    try:
        data = request.json
        original_title = data.get('original_title')
        new_title = data.get('new_title')
        new_description = data.get('new_description')
        
        if not all([original_title, new_title]):
            return jsonify({'error': 'Missing required fields'}), 400
            
        # Update all media items with the original title
        media_items = ButtonMedia.query.filter_by(title=original_title).all()
        if not media_items:
            return jsonify({'error': 'No media items found with the given title'}), 404
            
        for media in media_items:
            media.title = new_title
            if new_description is not None:
                media.description = new_description
            
        db.session.commit()
        return jsonify({'message': 'Successfully updated media titles'})
        
    except Exception as e:
        print(f"Error updating media titles: {str(e)}")
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/button-media/<int:media_id>', methods=['DELETE'])
def delete_button_media(media_id):
    """Delete button media"""
    media = ButtonMedia.query.get_or_404(media_id)
    
    try:
        # Delete the media file
        file_path = os.path.join(current_app.root_path, 'static', media.file_path)
        if os.path.exists(file_path):
            os.remove(file_path)
            
        db.session.delete(media)
        db.session.commit()
        return jsonify({'message': 'Media deleted successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/button-media/<int:media_id>', methods=['PUT'])
def update_button_media(media_id):
    """Update button media metadata"""
    media = ButtonMedia.query.get_or_404(media_id)
    data = request.json
    
    if not data.get('title'):
        return jsonify({'error': 'Title is required'}), 400
        
    try:
        media.title = data['title']
        media.description = data.get('description', media.description)
        media.updated_at = datetime.utcnow()
        
        db.session.commit()
        return jsonify({'message': 'Media updated successfully'})
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

@bp.route('/api/homes/<int:id>/details', methods=['PUT'])
def update_home_details(id):
    try:
        home = Home.query.get_or_404(id)
        data = request.get_json()

        if not data:
            return jsonify({'error': 'No data provided'}), 400

        # Update only title and description
        if 'title' in data:
            home.title = data['title']
        if 'description' in data:
            home.description = data['description']

        db.session.commit()

        return jsonify({
            'message': 'Home details updated successfully',
            'home': {
                'id': home.id,
                'title': home.title,
                'description': home.description
            }
        })

    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error updating home details: {str(e)}")
        return jsonify({'error': 'Failed to update home details'}), 500

@bp.route('/view-kiosks')
def view_kiosks():
    """Render the kiosk viewing page"""
    kiosks = Kiosk.query.order_by(Kiosk.created_at.desc()).all()
    return render_template('view_kiosks.html', kiosks=kiosks)

@bp.route('/api/buttons/<int:button_id>/media')
def get_button_media(button_id):
    """Get all media items for a button"""
    try:
        button = Button.query.get_or_404(button_id)
        media_items = ButtonMedia.query.filter_by(button_id=button_id).order_by(ButtonMedia.created_at.desc()).all()
        
        return jsonify({
            'button': {
                'id': button.id,
                'title': button.title
            },
            'media_items': [{
                'id': media.id,
                'type': media.type,
                'title': media.title,
                'description': media.description,
                'file_path': media.file_path
            } for media in media_items]
        })
    except Exception as e:
        current_app.logger.error(f"Error fetching button media: {str(e)}")
        return jsonify({'error': 'Failed to fetch button media'}), 500

