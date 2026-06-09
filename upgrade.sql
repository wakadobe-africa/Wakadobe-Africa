CREATE TABLE alembic_version (
    version_num VARCHAR(32) NOT NULL, 
    CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);

-- Running upgrade  -> efb5c68c1685

CREATE TABLE `admin` (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    email VARCHAR(120) NOT NULL, 
    password VARCHAR(255) NOT NULL, 
    `role` VARCHAR(20), 
    created_at DATETIME, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_admin_email ON `admin` (email);

CREATE TABLE category (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    PRIMARY KEY (id), 
    UNIQUE (name)
);

CREATE TABLE reader (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    email VARCHAR(120) NOT NULL, 
    created_at DATETIME, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_reader_email ON reader (email);

CREATE TABLE tag (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(50) NOT NULL, 
    PRIMARY KEY (id)
);

CREATE UNIQUE INDEX ix_tag_name ON tag (name);

CREATE TABLE subcategory (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    name VARCHAR(100) NOT NULL, 
    category_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(category_id) REFERENCES category (id)
);

CREATE INDEX ix_subcategory_category_id ON subcategory (category_id);

CREATE TABLE post (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    title VARCHAR(200) NOT NULL, 
    excerpt TEXT, 
    cover_image VARCHAR(255), 
    content TEXT NOT NULL, 
    created_at DATETIME, 
    admin_id INTEGER NOT NULL, 
    subcategory_id INTEGER, 
    reviewed_by INTEGER, 
    status VARCHAR(20), 
    is_oped BOOL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(admin_id) REFERENCES `admin` (id), 
    FOREIGN KEY(reviewed_by) REFERENCES `admin` (id), 
    FOREIGN KEY(subcategory_id) REFERENCES subcategory (id)
);

CREATE INDEX ix_post_admin_id ON post (admin_id);

CREATE INDEX ix_post_created_at ON post (created_at);

CREATE INDEX ix_post_status ON post (status);

CREATE INDEX ix_post_subcategory_id ON post (subcategory_id);

CREATE TABLE comment (
    id INTEGER NOT NULL AUTO_INCREMENT, 
    content TEXT NOT NULL, 
    created_at DATETIME, 
    is_approved BOOL, 
    reader_id INTEGER NOT NULL, 
    post_id INTEGER NOT NULL, 
    PRIMARY KEY (id), 
    FOREIGN KEY(post_id) REFERENCES post (id), 
    FOREIGN KEY(reader_id) REFERENCES reader (id)
);

CREATE INDEX ix_comment_post_id ON comment (post_id);

CREATE INDEX ix_comment_reader_id ON comment (reader_id);

CREATE TABLE post_tags (
    post_id INTEGER NOT NULL, 
    tag_id INTEGER NOT NULL, 
    PRIMARY KEY (post_id, tag_id), 
    FOREIGN KEY(post_id) REFERENCES post (id), 
    FOREIGN KEY(tag_id) REFERENCES tag (id)
);

INSERT INTO alembic_version (version_num) VALUES ('efb5c68c1685');

-- Running upgrade efb5c68c1685 -> 7b8c9d0e1f2a

ALTER TABLE comment ADD COLUMN flagged_at DATETIME;

CREATE INDEX ix_comment_flagged_at ON comment (flagged_at);

UPDATE alembic_version SET version_num='7b8c9d0e1f2a' WHERE alembic_version.version_num = 'efb5c68c1685';

-- Running upgrade 7b8c9d0e1f2a -> d3f91b7c4a2e

ALTER TABLE comment MODIFY is_approved BOOL NOT NULL DEFAULT true;

UPDATE comment SET is_approved = TRUE WHERE flagged_at IS NULL AND (is_approved IS NULL OR is_approved = FALSE);

UPDATE alembic_version SET version_num='d3f91b7c4a2e' WHERE alembic_version.version_num = '7b8c9d0e1f2a';

-- Running upgrade 7b8c9d0e1f2a -> a2c4f6e8b9d1

ALTER TABLE reader ADD COLUMN password VARCHAR(255);

INSERT INTO alembic_version (version_num) VALUES ('a2c4f6e8b9d1');

-- Running upgrade a2c4f6e8b9d1, d3f91b7c4a2e -> 94d44a04e624

DELETE FROM alembic_version WHERE alembic_version.version_num = 'a2c4f6e8b9d1';

UPDATE alembic_version SET version_num='94d44a04e624' WHERE alembic_version.version_num = 'd3f91b7c4a2e';

