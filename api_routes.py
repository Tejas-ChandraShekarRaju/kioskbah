from flask import Blueprint, request, jsonify, current_app
from models import db, Media, Button, ButtonMedia

api = Blueprint('api', __name__)

# ... existing routes ...

@api.route('/media/map-toggle', methods=['POST'])
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
        
        # Find all media with the given title
        media_items = Media.query.filter_by(title=title).all()
        
        if not media_items:
            return jsonify({"error": f"No media found with title '{title}'"}), 404
        
        if action == 'map':
            # Find button by subsection name (case insensitive)
            button = Button.query.filter(db.func.lower(Button.title) == db.func.lower(subsection_name)).first()
            
            if not button:
                return jsonify({"error": f"No button found with title matching '{subsection_name}'"}), 404
                
            # Map all media items to the button
            for media in media_items:
                # Check if mapping already exists
                existing_mapping = ButtonMedia.query.filter_by(
                    button_id=button.id, 
                    media_id=media.id
                ).first()
                
                if not existing_mapping:
                    # Create new mapping
                    new_mapping = ButtonMedia(
                        button_id=button.id,
                        media_id=media.id
                    )
                    db.session.add(new_mapping)
                    
                    # Update media with button ID for UI detection
                    media.button_id = button.id
            
            db.session.commit()
            return jsonify({
                "message": f"Successfully mapped {len(media_items)} media items to button",
                "button_id": button.id
            }), 200
            
        else:  # action == 'unmap'
            # Find and delete all mappings for these media items
            mapping_count = 0
            
            for media in media_items:
                # Find and delete all mappings
                mappings = ButtonMedia.query.filter_by(media_id=media.id).all()
                mapping_count += len(mappings)
                
                for mapping in mappings:
                    db.session.delete(mapping)
                
                # Clear button_id from media item
                media.button_id = None
            
            db.session.commit()
            return jsonify({
                "message": f"Successfully unmapped {mapping_count} button-media associations"
            }), 200
            
    except Exception as e:
        db.session.rollback()
        current_app.logger.error(f"Error in map_toggle_media: {str(e)}")
        return jsonify({"error": str(e)}), 500 