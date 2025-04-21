SECTIONS = [
    {
        'id': 1,
        'name': 'Architectural Elements',
        'icon': 'fa-solid fa-compass-drafting',
        'description': 'Core architectural components and design elements'
    },
    {
        'id': 2,
        'name': 'MEP Layouts',
        'icon': 'fa-solid fa-bolt',
        'description': 'Mechanical, Electrical, and Plumbing layouts and designs'
    },
    {
        'id': 3,
        'name': 'Structural Designs',
        'icon': 'fa-solid fa-building',
        'description': 'Structural components and engineering designs'
    },
    {
        'id': 4,
        'name': 'Construction Process',
        'icon': 'fa-solid fa-helmet-safety',
        'description': 'Step-by-step construction methodology'
    },
    {
        'id': 5,
        'name': 'Green Homes',
        'icon': 'fa-solid fa-comments',
        'description': 'Testimonials and project showcases'
    },
    {
        'id': 6,
        'name': 'Interior Design',
        'icon': 'fa-solid fa-couch',
        'description': 'Interior design concepts and implementations'
    },
    {
        'id': 7,
        'name': 'Value Added Services',
        'icon': 'fa-solid fa-pen-ruler',
        'description': 'Technical drawings and design specifications'
    }
]

def get_section_by_id(section_id):
    return next((section for section in SECTIONS if section['id'] == section_id), None)

FACING_OPTIONS = [
    'North',
    'South',
    'East',
    'West',
    'North East',
    'North West',
    'South East',
    'South West'
]

PLAN_TYPES = [
    'Residential',
    'Commercial',
    'Mixed Use',
    'Duplex',
    'Apartment',
    'Villa'
]

FLOOR_COUNT_OPTIONS = [
    'G+0.5',
    'G+1',
    'G+1.5',
    'G+2',
    'G+2.5',
    'G+3',
    'G+3.5',
    'G+4',
    'G+4.5',
    'G+5'
] 

SITE_DIMENSIONS = [
    '20 X 30',
    '30 X 30',
    '30 X 40',
    '30 X 50',
    '30 X 60',
    '40 X 40',
    '40 X 60',
    '50 X 60',
    '50 X 80',
    'Odd'
] 