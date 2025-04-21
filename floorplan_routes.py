from flask import Blueprint, render_template, request, jsonify, current_app
from werkzeug.utils import secure_filename
import os
from datetime import datetime
from models import db, FloorPlan
from constants import FACING_OPTIONS, PLAN_TYPES, FLOOR_COUNT_OPTIONS, SITE_DIMENSIONS
import logging
from helpers import send_to_s3, delete_from_s3

bp = Blueprint('floorplan', __name__)

ALLOWED_EXTENSIONS = {'png', 'jpg', 'jpeg', 'pdf'}

def allowed_file(filename):
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_EXTENSIONS

@bp.route('/manage-floorplans')
def manage_floorplans():
    plans = FloorPlan.query.order_by(FloorPlan.created_at.desc()).all()
    return render_template('manage_floorplan_and_elevation.html',
                         facing_options=FACING_OPTIONS,
                         plan_types=PLAN_TYPES,
                         floor_count_options=FLOOR_COUNT_OPTIONS,
                         site_dimensions=SITE_DIMENSIONS,
                         plans=plans)

@bp.route('/api/plans', methods=['GET'])
def get_plans():
    plans = FloorPlan.query.order_by(FloorPlan.created_at.desc()).all()
    return jsonify([plan.to_dict() for plan in plans])

@bp.route('/api/plans', methods=['POST'])
def create_plan():
    try:
        if 'floor_plan' not in request.files or 'elevation' not in request.files:
            return jsonify({'error': 'Both floor plan and elevation files are required'}), 400

        floor_plan = request.files['floor_plan']
        elevation = request.files['elevation']

        if floor_plan.filename == '' or elevation.filename == '':
            return jsonify({'error': 'No selected files'}), 400

        # Check file extensions
        floor_plan_ext = floor_plan.filename.rsplit('.', 1)[1].lower() if '.' in floor_plan.filename else ''
        elevation_ext = elevation.filename.rsplit('.', 1)[1].lower() if '.' in elevation.filename else ''
        
        # Floor plan can be image or PDF
        if not (floor_plan_ext in {'png', 'jpg', 'jpeg', 'pdf'}):
            return jsonify({'error': 'Invalid floor plan file type. Must be PNG, JPG, JPEG, or PDF'}), 400
            
        # Elevation must be an image only
        if not (elevation_ext in {'png', 'jpg', 'jpeg'}):
            return jsonify({'error': 'Invalid elevation file type. Must be PNG, JPG, or JPEG'}), 400

        # Upload floor plan to S3
        floor_plan_filename = secure_filename(f"{datetime.now().timestamp()}_fp_{floor_plan.filename}")
        result = send_to_s3(floor_plan, current_app.config['S3_BUCKET'], floor_plan_filename)
        
        if result != 'success':
            return jsonify({'error': f'Failed to upload floor plan: {result}'}), 500

        # Create S3 URL for floor plan
        s3_location = current_app.config['S3_LOCATION'].rstrip('/')
        floor_plan_url = f"{s3_location}/{floor_plan_filename}"

        # Upload elevation to S3
        elevation_filename = secure_filename(f"{datetime.now().timestamp()}_el_{elevation.filename}")
        result = send_to_s3(elevation, current_app.config['S3_BUCKET'], elevation_filename)
        
        if result != 'success':
            # Delete the floor plan since elevation upload failed
            delete_from_s3(floor_plan_url)
            return jsonify({'error': f'Failed to upload elevation: {result}'}), 500

        # Create S3 URL for elevation
        elevation_url = f"{s3_location}/{elevation_filename}"

        # Create new floor plan record
        new_plan = FloorPlan(
            site_dimension=request.form.get('site_dimension'),
            facing=request.form.get('facing'),
            type=request.form.get('type'),
            floors=request.form.get('floors'),
            floor_plan_path=floor_plan_url,
            elevation_path=elevation_url
        )

        db.session.add(new_plan)
        db.session.commit()

        return jsonify(new_plan.to_dict()), 201

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error creating plan: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/plans/<int:id>', methods=['GET'])
def get_plan(id):
    plan = FloorPlan.query.get_or_404(id)
    return jsonify(plan.to_dict())

@bp.route('/api/plans/<int:id>', methods=['DELETE'])
def delete_plan(id):
    try:
        plan = FloorPlan.query.get_or_404(id)

        # Delete files from S3
        if plan.floor_plan_path:
            result = delete_from_s3(plan.floor_plan_path)
            if result != 'success':
                logging.error(f"Error deleting floor plan from S3: {result}")

        if plan.elevation_path:
            result = delete_from_s3(plan.elevation_path)
            if result != 'success':
                logging.error(f"Error deleting elevation from S3: {result}")

        db.session.delete(plan)
        db.session.commit()

        return jsonify({'message': 'Floor plan deleted successfully'}), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error deleting plan: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/api/plans/<int:id>', methods=['PUT'])
def update_plan(id):
    try:
        plan = FloorPlan.query.get_or_404(id)
        
        # Update basic details only
        plan.site_dimension = request.form.get('site_dimension', plan.site_dimension)
        plan.facing = request.form.get('facing', plan.facing)
        plan.type = request.form.get('type', plan.type)
        plan.floors = request.form.get('floors', plan.floors)

        db.session.commit()
        return jsonify(plan.to_dict()), 200

    except Exception as e:
        db.session.rollback()
        logging.error(f"Error updating plan: {str(e)}")
        return jsonify({'error': str(e)}), 500

@bp.route('/check_floor_plan_and_elevation')
def check_floor_plan_and_elevation():
    """Render the floor plan and elevation view"""
    # Get query parameters
    site_dimension = request.args.get('site_dimension')
    facing = request.args.get('facing')
    floors = request.args.get('floors')
    use_type = request.args.get('use_type')
    view = request.args.get('view')

    # Base query
    query = FloorPlan.query

    # Apply filters if they exist
    if site_dimension:
        query = query.filter(FloorPlan.site_dimension == site_dimension)
    if facing:
        query = query.filter(FloorPlan.facing == facing)
    if floors:
        query = query.filter(FloorPlan.floors == floors)
    if use_type:
        query = query.filter(FloorPlan.type == use_type)

    # Get results ordered by creation date
    floor_plans_and_elevations = query.order_by(FloorPlan.created_at.desc()).all()

    # Convert to list of tuples for template
    plans_data = []
    for plan in floor_plans_and_elevations:
        # Ensure paths are properly formatted for display
        floor_plan_path = plan.floor_plan_path
        elevation_path = plan.elevation_path
        
        # If paths don't start with http/https, construct the full S3 URL
        if floor_plan_path and not (floor_plan_path.startswith('http://') or floor_plan_path.startswith('https://')):
            floor_plan_path = f"{current_app.config['S3_LOCATION'].rstrip('/')}/{floor_plan_path.lstrip('/')}"
        if elevation_path and not (elevation_path.startswith('http://') or elevation_path.startswith('https://')):
            elevation_path = f"{current_app.config['S3_LOCATION'].rstrip('/')}/{elevation_path.lstrip('/')}"

        plans_data.append((
            plan.id,
            plan.site_dimension,
            plan.facing,
            plan.type,
            plan.floors,
            floor_plan_path,
            elevation_path
        ))

    # Pass constants to template for dropdowns
    return render_template(
        'check_floor_plan_and_elevation.html',
        floor_plans_and_elevations=plans_data,
        no_floor_plans_and_elevations=len(plans_data) == 0,
        view_floor_plans=bool(view == 'featured' or any([site_dimension, facing, floors, use_type])),
        facing_options=FACING_OPTIONS,
        plan_types=PLAN_TYPES,
        floor_count_options=FLOOR_COUNT_OPTIONS,
        site_dimensions=SITE_DIMENSIONS
    )

@bp.route('/api/floor-plans/featured')
def get_featured_plans():
    """Get featured floor plans"""
    try:
        # Get all plans ordered by creation date
        plans = FloorPlan.query.order_by(FloorPlan.created_at.desc()).all()
        
        plans_data = []
        for plan in plans:
            # Ensure paths are properly formatted
            floor_plan_path = plan.floor_plan_path
            elevation_path = plan.elevation_path
            
            # If paths are S3 URLs, use them directly
            if not floor_plan_path.startswith('http'):
                floor_plan_path = f"{current_app.config['S3_LOCATION'].rstrip('/')}/{floor_plan_path}"
            if not elevation_path.startswith('http'):
                elevation_path = f"{current_app.config['S3_LOCATION'].rstrip('/')}/{elevation_path}"

            plans_data.append({
                'id': plan.id,
                'site_dimension': plan.site_dimension,
                'facing': plan.facing,
                'type': plan.type,
                'floors': plan.floors,
                'floor_plan_path': floor_plan_path,
                'elevation_path': elevation_path
            })

        return jsonify({
            'success': True,
            'data': plans_data
        })

    except Exception as e:
        logging.error(f"Error getting featured plans: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500

@bp.route('/api/floor-plans/search')
def search_floor_plans():
    """API endpoint for searching floor plans"""
    try:
        # Get query parameters
        site_dimension = request.args.get('site_dimension')
        facing = request.args.get('facing')
        floors = request.args.get('floors')
        use_type = request.args.get('use_type')

        # Base query
        query = FloorPlan.query

        # Apply filters
        if site_dimension:
            query = query.filter(FloorPlan.site_dimension == site_dimension)
        if facing:
            query = query.filter(FloorPlan.facing == facing)
        if floors:
            query = query.filter(FloorPlan.floors == floors)
        if use_type:
            query = query.filter(FloorPlan.type == use_type)

        # Get results
        results = query.order_by(FloorPlan.created_at.desc()).all()
        
        # Convert to list of dicts
        plans_data = []
        for plan in results:
            # Ensure paths are properly formatted
            floor_plan_path = plan.floor_plan_path
            elevation_path = plan.elevation_path
            
            # If paths are S3 URLs, use them directly
            if not floor_plan_path.startswith('http'):
                floor_plan_path = f"{current_app.config['S3_LOCATION'].rstrip('/')}/{floor_plan_path}"
            if not elevation_path.startswith('http'):
                elevation_path = f"{current_app.config['S3_LOCATION'].rstrip('/')}/{elevation_path}"

            plans_data.append({
                'id': plan.id,
                'site_dimension': plan.site_dimension,
                'facing': plan.facing,
                'type': plan.type,
                'floors': plan.floors,
                'floor_plan_path': floor_plan_path,
                'elevation_path': elevation_path
            })

        return jsonify({
            'success': True,
            'data': plans_data
        })

    except Exception as e:
        logging.error(f"Error searching floor plans: {str(e)}")
        return jsonify({
            'success': False,
            'error': str(e)
        }), 500 