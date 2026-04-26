# Wakadobe Africa Blog Platform - Comprehensive Documentation

## Overview

Wakadobe Africa is a comprehensive blogging platform built with Flask, designed for African professionals and entrepreneurs. The platform provides content management, user engagement features, and administrative tools for publishing articles on technology, business, leadership, and career development.

## Architecture

### Technology Stack
- **Backend**: Flask (Python web framework)
- **Database**: MySQL with SQLAlchemy ORM
- **Authentication**: Flask-WTF CSRF protection, Werkzeug password hashing
- **Rate Limiting**: Flask-Limiter
- **Database Migrations**: Flask-Migrate (Alembic)
- **Frontend**: Bootstrap 5, custom CSS, Jinja2 templates
- **Security**: CSRF protection, session management

### Project Structure
```
wakadobe-reads/
├── pkg/                          # Main application package
│   ├── __init__.py              # Flask app factory and configuration
│   ├── admin_routes.py          # Administrative interface routes
│   ├── blogmodel.py             # SQLAlchemy database models
│   ├── config.py                # Application configuration classes
│   ├── core_routes.py           # Core application routes (errors, newsletters)
│   ├── forms.py                 # WTForms form definitions
│   ├── limiter.py               # Rate limiting configuration
│   ├── reader_routes.py         # Public user-facing routes
│   ├── route_constants.py       # Session key constants
│   ├── static/                  # Static assets (CSS, JS, images)
│   │   ├── styles.css
│   │   ├── admin.css
│   │   └── bootstrap/
│   └── templates/               # Jinja2 templates
│       ├── admin/               # Admin interface templates
│       └── user/                # Public user templates
├── instance/                    # Instance-specific configuration
│   └── config.py               # Secret configuration (ignored by Git)
├── migrations/                  # Database migration files
├── requirements.txt             # Python dependencies
├── run.py                      # Application entry point
└── .gitignore                  # Git ignore patterns
```

## Database Models

### Admin Model
Represents administrative users who can create and manage content.

```python
class Admin(db.Model):
    id: Primary key
    name: String(100) - Admin's full name
    email: String(120) - Unique email address
    password: String(255) - Hashed password
    role: String(20) - Default "reader", can be "admin", "author", "contributor"
    created_at: DateTime - Account creation timestamp

    # Relationships
    posts: Posts authored by this admin
    reviewed_posts: Posts reviewed by this admin
```

### Post Model
Core content model for blog articles.

```python
class Post(db.Model):
    id: Primary key
    title: String(200) - Article title
    excerpt: Text - Optional article summary
    cover_image: String(255) - Path to cover image
    content: Text - Full article content (HTML)
    created_at: DateTime - Publication timestamp

    # Foreign Keys
    admin_id: References Admin.id (author)
    subcategory_id: References Subcategory.id (optional)
    reviewed_by: References Admin.id (optional reviewer)

    # Publishing
    status: String(20) - "draft" or "published"
    is_oped: Boolean - Opinion/editorial piece flag

    # Relationships
    tags: Many-to-many relationship with Tag model
    comments: One-to-many relationship with Comment model
```

### Category & Subcategory Models
Hierarchical content organization.

```python
class Category(db.Model):
    id: Primary key
    name: String(100) - Unique category name
    # Note: 'type' field for grouping is NOT currently implemented

    # Relationships
    subcategories: One-to-many with Subcategory

class Subcategory(db.Model):
    id: Primary key
    name: String(100) - Subcategory name
    category_id: References Category.id

    # Relationships
    posts: One-to-many with Post
```

### Tag Model
Flexible content tagging system.

```python
class Tag(db.Model):
    id: Primary key
    name: String(50) - Unique tag name

    # Relationships (many-to-many with posts via post_tags table)
    posts: Dynamic relationship with Post model
```

### Reader Model
Public users who can comment and interact with content.

```python
class Reader(db.Model):
    id: Primary key
    name: String(100) - Reader's display name
    email: String(120) - Unique email address
    password: String(255) - Optional hashed password
    created_at: DateTime - Registration timestamp

    # Relationships
    comments: One-to-many with Comment model
```

### Comment Model
User engagement through comments.

```python
class Comment(db.Model):
    id: Primary key
    content: Text - Comment text
    created_at: DateTime - Comment timestamp
    is_approved: Boolean - Moderation status
    flagged_at: DateTime - When comment was flagged (optional)

    # Foreign Keys
    reader_id: References Reader.id
    post_id: References Post.id
```

## Core Functionality

### Public User Features

#### Content Browsing
- **Homepage** (`/`): Displays published posts in reverse chronological order
- **Category Browsing** (`/wakadobe/category/<category_id>`): Posts filtered by category
- **Subcategory Browsing** (`/wakadobe/subcategories/<subcategory_id>/posts`): Posts filtered by subcategory
- **Individual Post View** (`/wakadobe/posts/<post_id>`): Full article with comments

#### User Authentication
- **Registration** (`/wakadobe/readers/sign-up`): New user account creation
- **Login** (`/wakadobe/readers/login`): User authentication
- **Password Reset** (`/wakadobe/readers/reset-password`): Password recovery
- **Logout** (`/wakadobe/readers/log-out`): Session termination

#### Social Features
- **Comments**: Authenticated users can comment on posts
- **Social Sharing**: Share buttons for LinkedIn, X (Twitter), Discord, WhatsApp
- **Related Content**: Related posts displayed on article pages

#### Static Pages
- **About Page** (`/wakadobe/about`): Information about the blog
- **Newsletters** (`/newsletters`): Placeholder for future newsletter functionality

### Administrative Features

#### Authentication & Access Control
- **Admin Login** (`/wakadobe/admin/login`): Administrative authentication
- **Session Management**: Admin sessions tracked via `ADMIN_SESSION_KEY`

#### Content Management
- **Post Creation** (`/wakadobe/admin/create-post`): Create new articles
- **Draft Management** (`/wakadobe/admin/drafts`): View and manage draft posts
- **Post Preview** (`/wakadobe/admin/drafts/<post_id>/preview`): Preview draft articles

#### Taxonomy Management
- **Category CRUD** (`/wakadobe/admin/categories`):
  - Create, update, delete categories
  - Note: Type assignment for grouping is NOT currently implemented
- **Subcategory CRUD**: Create and manage subcategories within categories
- **Tag CRUD**: Create and manage content tags

#### User Management
- **Account Creation** (`/wakadobe/admin/create-account`): Create new admin accounts
- **Settings** (`/wakadobe/admin/settings`): Application configuration

#### Moderation
- **Comment Management** (`/wakadobe/admin/comments`):
  - View all comments
  - Approve/reject comments
  - Flag inappropriate content
  - Purge flagged comments

## Route Logic & Flow

### Public Routes (reader_routes.py)

#### Homepage (`/`)
```python
@app.route("/")
def wakadobe_index():
    # Query published posts, ordered by creation date
    # Paginate results (implicit in template)
    # Render index template with posts
```

#### Category Posts (`/wakadobe/category/<category_id>`)
```python
@app.route("/wakadobe/category/<int:category_id>")
def category_posts(category_id):
    # Validate category exists
    # Query posts in category's subcategories
    # Order by creation date
    # Render category template
```

#### Subcategory Posts (`/wakadobe/subcategories/<subcategory_id>/posts`)
```python
@app.route("/wakadobe/subcategories/<int:subcategory_id>/posts")
def subcategory_posts(subcategory_id):
    # Validate subcategory exists
    # Query published posts in subcategory
    # Render subcategory template
```

#### Individual Post (`/wakadobe/posts/<post_id>`)
```python
@app.route("/wakadobe/posts/<int:post_id>")
def post_details(post_id):
    # Validate post exists and is published
    # Load approved comments
    # Find related posts (same subcategory or general)
    # Render post template with comments and related content
```

#### Comment Submission (`/wakadobe/posts/<post_id>/comment`)
```python
@app.route("/wakadobe/posts/<int:post_id>/comment", methods=["POST"])
def add_comment(post_id):
    # Require reader authentication
    # Validate post exists
    # Create new comment (auto-approved)
    # Redirect to post with success message
```

#### User Authentication Routes
- **Sign Up**: Form validation, password hashing, account creation
- **Login**: Credential verification, session establishment
- **Password Reset**: Email-based password recovery
- **Logout**: Session cleanup

### Admin Routes (admin_routes.py)

#### Dashboard (`/wakadobe/admin`)
- Overview statistics and recent activity
- Post counts, comment moderation status

#### Content Creation (`/wakadobe/admin/create-post`)
- Multi-step form for article creation
- Category/subcategory/tag selection
- Draft/publish options
- Image upload handling

#### Taxonomy Management
- **Categories**: CRUD operations with type assignment
- **Subcategories**: CRUD with category association
- **Tags**: Simple CRUD operations

#### Moderation (`/wakadobe/admin/comments`)
- Comment approval workflow
- Flagging system for inappropriate content
- Bulk operations for flagged comments

### Core Routes (core_routes.py)

#### Error Handling
- **404 Handler**: Custom "Page Not Found" template
- **500 Handler**: Custom "Internal Server Error" template

#### Feature Placeholders
- **Newsletters** (`/newsletters`): Returns 404 with "Coming Soon" message

## Security Features

### Authentication & Authorization
- **CSRF Protection**: Flask-WTF CSRF tokens on all forms
- **Password Security**: Werkzeug PBKDF2 hashing
- **Session Management**: Secure session handling with unique keys
- **Rate Limiting**: 120 requests per hour per IP address

### Data Validation
- **Form Validation**: WTForms for input sanitization
- **HTML Stripping**: XSS prevention on user content
- **Email Validation**: Proper email format checking

### Access Control
- **Admin Routes**: Session-based authentication required
- **Reader Features**: Optional authentication for comments
- **Content Filtering**: Only published posts visible to public

## Configuration

### Application Configuration (pkg/config.py)
```python
class General:
    APP_NAME = 'wakadobeblog'
    SQLALCHEMY_TRACK_MODIFICATIONS = False
    RATELIMIT_DEFAULT = '120 per hour'  # Configured but limiter uses empty defaults
    RATELIMIT_STORAGE_URI = 'memory://'
    RATELIMIT_HEADERS_ENABLED = True

class LiveConfig(General):
    DATABASE = 'wakadobedb'
```

### Instance Configuration (instance/config.py)
- **SECRET_KEY**: Flask application secret key
- **SQLALCHEMY_DATABASE_URI**: Database connection string
- **Git-ignored**: Contains sensitive configuration

### Environment Variables
- Support for `.env` files (python-dotenv)
- Environment variable overrides for configuration

## Template Structure

### Base Template (user/base.html)
- HTML5 structure with Bootstrap 5
- SEO meta tags (title, description, Open Graph, Twitter Cards)
- Navigation with single category dropdown ("Wakadobe digest")
- Footer with site information
- CSRF token injection for forms

### User Templates
- **index.html**: Homepage with post grid
- **post_contents.html**: Individual article with comments and sharing
- **category_posts.html**: Category-specific post listings
- **reader_login.html/reader_signup.html**: Authentication forms

### Admin Templates
- **dashboard.html**: Admin overview and statistics
- **create_post.html**: Article creation form
- **categories.html**: Taxonomy management interface
- **comments.html**: Comment moderation interface

## Data Flow & Business Logic

### Content Publishing Workflow
1. **Draft Creation**: Admin creates post in draft status
2. **Review Process**: Optional admin review and approval
3. **Publication**: Status changed to "published"
4. **Public Access**: Published posts appear on homepage and category pages

### Comment Moderation
1. **Submission**: Readers submit comments (auto-approved)
2. **Moderation**: Admins can approve/reject comments
3. **Flagging**: Inappropriate comments can be flagged for review
4. **Cleanup**: Flagged comments can be bulk-deleted

### User Engagement
1. **Registration**: Optional user accounts for commenting
2. **Authentication**: Session-based login system
3. **Interaction**: Comments, social sharing, content browsing
4. **Personalization**: User-specific features (comment history, preferences)

## Deployment Considerations

### Production Requirements
- **WSGI Server**: Gunicorn or uWSGI for production serving
- **Database**: MySQL production instance
- **File Storage**: Cloud storage for uploaded images
- **Email Service**: SMTP service for password resets
- **SSL/TLS**: HTTPS certificate for secure connections

### Environment Setup
- **Virtual Environment**: Isolated Python environment
- **Dependencies**: Install from requirements.txt
- **Database**: Run migrations with `flask db upgrade`
- **Static Files**: Configure web server for static asset serving

### Security Checklist
- [ ] Change default SECRET_KEY
- [ ] Use strong database credentials
- [ ] Enable HTTPS in production
- [ ] Configure proper CORS if needed
- [ ] Set up monitoring and logging
- [ ] Regular security updates for dependencies

## Development Workflow

### Local Development
1. **Setup**: `python -m venv venv && source venv/bin/activate`
2. **Install**: `pip install -r requirements.txt`
3. **Configure**: Set up `instance/config.py` with local database
4. **Migrate**: `flask db upgrade`
5. **Run**: `python run.py`

### Code Organization
- **Separation of Concerns**: Routes, models, and templates clearly separated
- **Modular Design**: Feature-specific route files
- **Template Inheritance**: DRY principle with base templates
- **Configuration Management**: Environment-specific settings

### Testing Strategy
- **Unit Tests**: Model and utility function testing
- **Integration Tests**: Route and database interaction testing
- **UI Tests**: Template rendering and user flow validation

## Implementation Status Notes

### ✅ Implemented Features
- Complete database models (Admin, Post, Category, Subcategory, Tag, Reader, Comment)
- All documented routes and endpoints
- User authentication and session management
- CSRF protection with error handling
- Rate limiting configuration
- Social sharing buttons (LinkedIn, X, Discord, WhatsApp)
- SEO meta tags and Open Graph support
- Admin dashboard and content management
- Comment system with moderation
- Secure configuration with instance/config.py

### ❌ Not Yet Implemented
- Category type field for grouping (documented but not in models/routes)
- Category grouping by type in navigation (single dropdown only)
- Advanced search functionality
- Newsletter system (placeholder route only)
- User profiles and advanced personalization
- Analytics and performance monitoring
- API endpoints
- Multilingual support

### 🔄 Partially Implemented
- Rate limiting: Configured but limiter uses empty default limits
- Taxonomy management: Basic CRUD without type-based organization

## Future Enhancements

### High Priority (Not Yet Implemented)
- **Category Type System**: Add type field to categories for logical grouping
- **Advanced Navigation**: Group categories by type in navbar dropdowns
- **Newsletter System**: Email subscription and delivery functionality
- **Advanced Search**: Full-text search with filters and faceting
- **User Profiles**: Reader dashboard and preferences
- **Analytics**: Content performance tracking and insights

### Medium Priority
- **API Endpoints**: RESTful API for mobile applications
- **Enhanced Moderation**: Advanced comment filtering and spam detection
- **Content Scheduling**: Automated publishing and draft scheduling

### Technical Improvements
- **Caching**: Redis for session and content caching
- **CDN**: Content delivery network for static assets
- **Monitoring**: Application performance monitoring
- **Backup**: Automated database backups
- **Scalability**: Horizontal scaling considerations
- **Multilingual Support**: Localization and internationalization

---

This documentation provides a comprehensive overview of the Wakadobe Africa blogging platform. For specific implementation details or troubleshooting, refer to the inline code comments and Flask documentation.