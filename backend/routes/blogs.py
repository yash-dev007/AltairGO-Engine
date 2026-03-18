"""
blogs.py — Public blog listing + Admin CRUD for BlogPost.
Public:  GET /blogs, GET /blogs/<id>
Admin:   POST/PUT/DELETE /api/admin/blogs[/<id>]
"""

from flask import Blueprint, request, jsonify
from backend.database import db
from backend.models import BlogPost
from backend.utils.auth import require_admin

blogs_bp = Blueprint('blogs', __name__)


# ── Helpers ───────────────────────────────────────────────────────

def _parse_body():
    data = request.get_json(silent=True) or {}
    return {
        'title':     data.get('title', '').strip(),
        'category':  data.get('category', '').strip(),
        'date':      data.get('date', '').strip(),
        'read_time': data.get('readTime', data.get('read_time', '')).strip(),
        'image':     data.get('image', '').strip(),
        'excerpt':   data.get('excerpt', '').strip(),
        'content':   data.get('content', ''),
        'tags':      data.get('tags') or [],
        'author':    data.get('author', '').strip(),
        'published': bool(data.get('published', True)),
    }


# ── Public ────────────────────────────────────────────────────────

@blogs_bp.route('/blogs', methods=['GET'])
def list_blogs():
    posts = (
        db.session.query(BlogPost)
        .filter(BlogPost.published == True)
        .order_by(BlogPost.id.desc())
        .all()
    )
    return jsonify([p.to_dict() for p in posts]), 200


@blogs_bp.route('/blogs/<int:post_id>', methods=['GET'])
def get_blog(post_id):
    post = db.session.query(BlogPost).filter(
        BlogPost.id == post_id,
        BlogPost.published == True,
    ).first()
    if not post:
        return jsonify({'error': 'Not found'}), 404
    return jsonify(post.to_dict()), 200


# ── Admin CRUD ────────────────────────────────────────────────────

@blogs_bp.route('/api/admin/blogs', methods=['GET'])
@require_admin
def admin_list_blogs():
    """Return all posts (including unpublished) for the admin panel."""
    posts = db.session.query(BlogPost).order_by(BlogPost.id.desc()).all()
    return jsonify([p.to_dict() for p in posts]), 200


@blogs_bp.route('/api/admin/blogs', methods=['POST'])
@require_admin
def admin_create_blog():
    data = _parse_body()
    if not data['title']:
        return jsonify({'error': 'title is required'}), 400
    post = BlogPost(**data)
    db.session.add(post)
    db.session.commit()
    return jsonify({'message': 'Blog post created', 'id': post.id, 'post': post.to_dict()}), 201


@blogs_bp.route('/api/admin/blogs/<int:post_id>', methods=['PUT'])
@require_admin
def admin_update_blog(post_id):
    post = db.session.get(BlogPost, post_id)
    if not post:
        return jsonify({'error': 'Not found'}), 404
    data = _parse_body()
    if not data['title']:
        return jsonify({'error': 'title is required'}), 400
    for key, val in data.items():
        setattr(post, key, val)
    db.session.commit()
    return jsonify({'message': 'Updated', 'post': post.to_dict()}), 200


@blogs_bp.route('/api/admin/blogs/<int:post_id>', methods=['DELETE'])
@require_admin
def admin_delete_blog(post_id):
    post = db.session.get(BlogPost, post_id)
    if not post:
        return jsonify({'error': 'Not found'}), 404
    db.session.delete(post)
    db.session.commit()
    return jsonify({'message': 'Deleted'}), 200
