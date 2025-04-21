from flask import Blueprint,render_template, jsonify, request, current_app,flash, redirect, url_for
from werkzeug.utils import secure_filename
import time
from models import db, Home, HomeMedia
from helpers import allowed_file, send_to_s3, delete_from_s3

bp = Blueprint('home', __name__)

@bp.route('/view-homes')
def view_homes():
    """Route to display all homes in a grid layout."""
    try:
        # Get all homes with their media items
        homes = Home.query.order_by(Home.created_at.desc()).all()
        return render_template('view_homes.html', homes=homes)
    except Exception as e:
        current_app.logger.error(f"Error in view_homes: {str(e)}")
        flash('An error occurred while loading homes.', 'error')
        return redirect(url_for('kiosk.check_floor_plan_and_elevation')) 

@bp.route('/manage-homes')
def manage_homes():
    homes = Home.query.order_by(Home.created_at.desc()).all()
    return render_template('manage_homes.html', homes=homes) 

@bp.route('/api/homes', methods=['POST'])
def create_home():
    if not all(x in request.files for x in ['photos', 'floor_plan', 'isometric']):
        return jsonify({'error': 'Missing required files'}), 400

    title = request.form.get('title')
    description = request.form.get('description', '')

    if not title:
        return jsonify({'error': 'Title is required'}), 400

    try:
        # Create home record
        home = Home(title=title, description=description)
        db.session.add(home)
        db.session.flush()  # Get the home ID

        bucket_name = current_app.config['S3_BUCKET']
        uploaded_media = []

        # Handle photos (multiple)
        photos = request.files.getlist('photos')
        for photo in photos:
            if photo and allowed_file(photo.filename):
                filename = secure_filename(photo.filename)
                unique_filename = f"homes/{home.id}/photos/{int(time.time())}_{filename}"
                
                result = send_to_s3(photo, bucket_name, unique_filename)
                if result != 'success':
                    raise Exception(f"Failed to upload photo to S3: {result}")

                s3_location = current_app.config['S3_LOCATION'].rstrip('/')
                file_path = f"{s3_location}/{unique_filename}"

                media = HomeMedia(
                    home_id=home.id,
                    media_type='photo',
                    file_path=file_path
                )
                db.session.add(media)
                uploaded_media.append(file_path)

        # Handle floor plan (single)
        floor_plan = request.files['floor_plan']
        if floor_plan and allowed_file(floor_plan.filename):
            filename = secure_filename(floor_plan.filename)
            unique_filename = f"homes/{home.id}/floor_plan/{filename}"
            
            result = send_to_s3(floor_plan, bucket_name, unique_filename)
            if result != 'success':
                raise Exception(f"Failed to upload floor plan to S3: {result}")

            s3_location = current_app.config['S3_LOCATION'].rstrip('/')
            file_path = f"{s3_location}/{unique_filename}"

            media = HomeMedia(
                home_id=home.id,
                media_type='floor_plan',
                file_path=file_path
            )
            db.session.add(media)
            uploaded_media.append(file_path)

        # Handle isometric view (single)
        isometric = request.files['isometric']
        if isometric and allowed_file(isometric.filename):
            filename = secure_filename(isometric.filename)
            unique_filename = f"homes/{home.id}/isometric/{filename}"
            
            result = send_to_s3(isometric, bucket_name, unique_filename)
            if result != 'success':
                raise Exception(f"Failed to upload isometric view to S3: {result}")

            s3_location = current_app.config['S3_LOCATION'].rstrip('/')
            file_path = f"{s3_location}/{unique_filename}"

            media = HomeMedia(
                home_id=home.id,
                media_type='isometric',
                file_path=file_path
            )
            db.session.add(media)
            uploaded_media.append(file_path)

        # Handle video (optional)
        if 'video' in request.files:
            video = request.files['video']
            if video and allowed_file(video.filename):
                filename = secure_filename(video.filename)
                unique_filename = f"homes/{home.id}/video/{filename}"
                
                result = send_to_s3(video, bucket_name, unique_filename)
                if result != 'success':
                    raise Exception(f"Failed to upload video to S3: {result}")

                s3_location = current_app.config['S3_LOCATION'].rstrip('/')
                file_path = f"{s3_location}/{unique_filename}"

                media = HomeMedia(
                    home_id=home.id,
                    media_type='video',
                    file_path=file_path
                )
                db.session.add(media)
                uploaded_media.append(file_path)

        db.session.commit()
        return jsonify({
            'message': 'Home created successfully',
            'home_id': home.id,
            'uploaded_media': uploaded_media
        })

    except Exception as e:
        db.session.rollback()
        print(f"Error creating home: {str(e)}")
        return jsonify({'error': str(e)}), 500 

@bp.route('/api/homes/<int:id>', methods=['GET'])
def get_home(id):
    home = Home.query.get_or_404(id)
    return jsonify({
        'id': home.id,
        'title': home.title,
        'description': home.description,
        'created_at': home.created_at.isoformat(),
        'media_items': [{
            'id': media.id,
            'media_type': media.media_type,
            'file_path': media.file_path
        } for media in home.media_items]
    })

@bp.route('/api/homes/<int:id>', methods=['DELETE'])
def delete_home(id):
    home = Home.query.get_or_404(id)
    
    try:
        # Delete all media files from S3
        for media in home.media_items:
            delete_from_s3(media.file_path)
        
        # Delete home and all associated media (cascade will handle this)
        db.session.delete(home)
        db.session.commit()
        
        return jsonify({'message': 'Home deleted successfully'})
    except Exception as e:
        db.session.rollback()
        print(f"Error deleting home: {str(e)}")
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