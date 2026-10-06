BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('202610061200');
CREATE TABLE app_meta (
	id INTEGER NOT NULL, 
	auth_epoch INTEGER NOT NULL, 
	password_fp VARCHAR(64), 
	secret_key_check VARCHAR(64), 
	last_boot_version VARCHAR(32), 
	CONSTRAINT pk_app_meta PRIMARY KEY (id), 
	CONSTRAINT ck_app_meta_single_row CHECK (id = 1)
);
INSERT INTO "app_meta" VALUES(1,3,NULL,NULL,'0.1.0');
CREATE TABLE devices (
	id VARCHAR(36) NOT NULL, 
	label VARCHAR(80) NOT NULL, 
	member_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	last_seen_at DATETIME NOT NULL, 
	revoked_at DATETIME, 
	CONSTRAINT pk_devices PRIMARY KEY (id), 
	CONSTRAINT fk_devices_member_id_members FOREIGN KEY(member_id) REFERENCES members (id) ON DELETE SET NULL
);
INSERT INTO "devices" VALUES('00000000-0000-7000-8000-0000000000d1','iPhone','00000000-0000-7000-8000-000000000001','2026-10-06 12:00:00','2026-10-06 12:30:00',NULL);
INSERT INTO "devices" VALUES('00000000-0000-7000-8000-0000000000d2','Android phone',NULL,'2026-10-06 12:05:00','2026-10-06 12:06:00','2026-10-06 12:40:00');
CREATE TABLE household (
	id INTEGER NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	active_store_id VARCHAR(36), 
	default_cart_modality VARCHAR(16) NOT NULL, 
	price_max_age_minutes INTEGER NOT NULL, 
	updated_at DATETIME NOT NULL, 
	CONSTRAINT pk_household PRIMARY KEY (id), 
	CONSTRAINT ck_household_single_row CHECK (id = 1)
);
INSERT INTO "household" VALUES(1,'Sample household',NULL,'PICKUP',120,'2026-10-06 21:24:30');
CREATE TABLE members (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(40) NOT NULL, 
	marker_color VARCHAR(16) NOT NULL, 
	sort INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	archived_at DATETIME, 
	CONSTRAINT pk_members PRIMARY KEY (id)
);
INSERT INTO "members" VALUES('00000000-0000-7000-8000-000000000001','Sample Parent','basil',0,'2026-10-06 12:00:00',NULL);
INSERT INTO "members" VALUES('00000000-0000-7000-8000-000000000002','Sample Kid','tomato',1,'2026-10-06 12:01:00',NULL);
INSERT INTO "members" VALUES('00000000-0000-7000-8000-000000000003','Sample Guest','plum',2,'2026-10-06 12:02:00','2026-10-06 13:00:00');
COMMIT;
