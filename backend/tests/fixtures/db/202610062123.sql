BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('202610062123');
CREATE TABLE app_meta (
	id INTEGER NOT NULL, 
	auth_epoch INTEGER NOT NULL, 
	password_fp VARCHAR(64), 
	secret_key_check VARCHAR(64), 
	last_boot_version VARCHAR(32), 
	CONSTRAINT pk_app_meta PRIMARY KEY (id), 
	CONSTRAINT ck_app_meta_single_row CHECK (id = 1)
);
INSERT INTO "app_meta" VALUES(1,3,NULL,NULL,'0.2.0');
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
CREATE TABLE dish_items (
	id VARCHAR(36) NOT NULL, 
	dish_id VARCHAR(36) NOT NULL, 
	item_id VARCHAR(36) NOT NULL, 
	amount_kind VARCHAR(16) NOT NULL, 
	amount VARCHAR(32) NOT NULL, 
	unit VARCHAR(8), 
	position INTEGER NOT NULL, 
	CONSTRAINT pk_dish_items PRIMARY KEY (id), 
	CONSTRAINT fk_dish_items_dish_id_dishes FOREIGN KEY(dish_id) REFERENCES dishes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_dish_items_item_id_items FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE RESTRICT
);
INSERT INTO "dish_items" VALUES('00000000-0000-7000-8000-000000000501','00000000-0000-7000-8000-000000000401','00000000-0000-7000-8000-000000000301','packages','1',NULL,0);
INSERT INTO "dish_items" VALUES('00000000-0000-7000-8000-000000000502','00000000-0000-7000-8000-000000000401','00000000-0000-7000-8000-000000000302','count','2',NULL,1);
INSERT INTO "dish_items" VALUES('00000000-0000-7000-8000-000000000503','00000000-0000-7000-8000-000000000402','00000000-0000-7000-8000-000000000303','measure','1','tbsp',0);
INSERT INTO "dish_items" VALUES('00000000-0000-7000-8000-000000000504','00000000-0000-7000-8000-000000000403','00000000-0000-7000-8000-000000000303','measure','1/3','cup',0);
CREATE TABLE dishes (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	role VARCHAR(8) NOT NULL, 
	occasions JSON NOT NULL, 
	servings INTEGER, 
	photo_id VARCHAR(36), 
	notes TEXT, 
	recipe_url VARCHAR(500), 
	favorite BOOLEAN NOT NULL, 
	last_planned_at DATETIME, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	archived_at DATETIME, 
	CONSTRAINT pk_dishes PRIMARY KEY (id), 
	CONSTRAINT fk_dishes_photo_id_photos FOREIGN KEY(photo_id) REFERENCES photos (id) ON DELETE SET NULL
);
INSERT INTO "dishes" VALUES('00000000-0000-7000-8000-000000000401','Tacos','main','["dinner"]',4,'00000000-0000-7000-8000-000000000201','Warm the shells.','https://example.com/tacos',1,NULL,'2026-10-06 12:40:00','2026-10-06 12:40:00',NULL);
INSERT INTO "dishes" VALUES('00000000-0000-7000-8000-000000000402','Rice','side','["dinner","lunch"]',NULL,NULL,NULL,NULL,0,NULL,'2026-10-06 12:41:00','2026-10-06 12:41:00',NULL);
INSERT INTO "dishes" VALUES('00000000-0000-7000-8000-000000000403','Soup','main','[]',NULL,NULL,NULL,NULL,0,NULL,'2026-10-06 12:42:00','2026-10-06 12:42:00','2026-10-06 13:10:00');
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
INSERT INTO "household" VALUES(1,'Sample household','00000000-0000-7000-8000-000000000101','PICKUP',120,'2026-10-06 12:10:00');
CREATE TABLE items (
	id VARCHAR(36) NOT NULL, 
	name VARCHAR(80) NOT NULL, 
	product_id VARCHAR(16), 
	upc VARCHAR(16), 
	size_text VARCHAR(80), 
	size_source VARCHAR(16) NOT NULL, 
	sold_by VARCHAR(8), 
	each_weight_lb VARCHAR(32), 
	is_staple BOOLEAN NOT NULL, 
	section_override_key VARCHAR(64), 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	archived_at DATETIME, 
	CONSTRAINT pk_items PRIMARY KEY (id)
);
INSERT INTO "items" VALUES('00000000-0000-7000-8000-000000000301','Ground beef','0000000000001','0000000000001','1 lb','parsed','UNIT',NULL,0,NULL,'2026-10-06 12:30:00','2026-10-06 12:30:00',NULL);
INSERT INTO "items" VALUES('00000000-0000-7000-8000-000000000302','Bananas','0000000000002','0000000000002',NULL,'parsed','WEIGHT','3/8',0,NULL,'2026-10-06 12:31:00','2026-10-06 12:31:00',NULL);
INSERT INTO "items" VALUES('00000000-0000-7000-8000-000000000303','Cooking oil','0000000000003','0000000000003','48 fl oz','household','UNIT',NULL,1,'aisle:12','2026-10-06 12:32:00','2026-10-06 12:32:00',NULL);
INSERT INTO "items" VALUES('00000000-0000-7000-8000-000000000304','Birthday candles',NULL,NULL,NULL,'parsed',NULL,NULL,0,NULL,'2026-10-06 12:33:00','2026-10-06 12:33:00','2026-10-06 13:00:00');
CREATE TABLE kroger_api_usage (
	api VARCHAR(16) NOT NULL, 
	window_started_at DATETIME, 
	calls INTEGER NOT NULL, 
	blocked_until DATETIME, 
	last_429_at DATETIME, 
	probe_backoff_s INTEGER, 
	CONSTRAINT pk_kroger_api_usage PRIMARY KEY (api)
);
INSERT INTO "kroger_api_usage" VALUES('products','2026-10-06 12:00:00',42,NULL,NULL,NULL);
INSERT INTO "kroger_api_usage" VALUES('locations','2026-10-06 12:05:00',3,'2026-10-07 12:05:00','2026-10-06 12:06:00',60);
CREATE TABLE kroger_product_cache (
	product_id VARCHAR(16) NOT NULL, 
	location_id VARCHAR(16) NOT NULL, 
	payload TEXT NOT NULL, 
	fetched_at DATETIME NOT NULL, 
	expires_at DATETIME NOT NULL, 
	cache_control_raw VARCHAR(200) NOT NULL, 
	CONSTRAINT pk_kroger_product_cache PRIMARY KEY (product_id, location_id)
);
INSERT INTO "kroger_product_cache" VALUES('0000000000001','99999001','{"product_id":"0000000000001","upc":"0000000000001","description":"Sample Ground Beef","brand":"Sample","categories":["Meat & Seafood"],"page_uri":"/p/sample-ground-beef/0000000000001","image":null,"size":"1 lb","sold_by":"UNIT","price":{"regular":549,"promo":499,"each_estimate":null,"effective":"2026-10-01T04:00:00+00:00","expires":"2026-10-08T03:59:59+00:00"},"stock_level":"HIGH","in_store":true,"aisles":[{"number":null,"side":null,"description":"MEAT","bay":null}]}','2026-10-06 12:50:00','2026-10-06 13:50:00','max-age=3600');
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
CREATE TABLE photos (
	id VARCHAR(36) NOT NULL, 
	webp BLOB NOT NULL, 
	thumb BLOB NOT NULL, 
	width INTEGER NOT NULL, 
	height INTEGER NOT NULL, 
	created_at DATETIME NOT NULL, 
	CONSTRAINT pk_photos PRIMARY KEY (id)
);
INSERT INTO "photos" VALUES('00000000-0000-7000-8000-000000000201',X'52494646320000005745425056503820260000007001009D012A0400030003805A25A0027401400000FEE88B1F8DFEAD7C9929B565A886FC0000',X'52494646320000005745425056503820260000007001009D012A0200020003805A25A0027401400000FEE88B1F8DFEAD7C9929B565A886FC0000',4,3,'2026-10-06 12:20:00');
CREATE TABLE store_sections (
	id VARCHAR(36) NOT NULL, 
	store_id VARCHAR(36) NOT NULL, 
	"key" VARCHAR(64) NOT NULL, 
	label VARCHAR(120) NOT NULL, 
	sort_index INTEGER NOT NULL, 
	hidden BOOLEAN NOT NULL, 
	CONSTRAINT pk_store_sections PRIMARY KEY (id), 
	CONSTRAINT fk_store_sections_store_id_stores FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE CASCADE, 
	CONSTRAINT uq_store_sections_store_id UNIQUE (store_id, "key")
);
INSERT INTO "store_sections" VALUES('00000000-0000-7000-8000-000000000111','00000000-0000-7000-8000-000000000101','cat:produce','Produce',100,0);
INSERT INTO "store_sections" VALUES('00000000-0000-7000-8000-000000000112','00000000-0000-7000-8000-000000000101','aisle:12','Aisle 12',1012,0);
INSERT INTO "store_sections" VALUES('00000000-0000-7000-8000-000000000113','00000000-0000-7000-8000-000000000101','cat:other','Other',9900,1);
CREATE TABLE stores (
	id VARCHAR(36) NOT NULL, 
	location_id VARCHAR(16) NOT NULL, 
	chain VARCHAR(64) NOT NULL, 
	name VARCHAR(120) NOT NULL, 
	address_line1 VARCHAR(120), 
	address_line2 VARCHAR(120), 
	city VARCHAR(80), 
	state VARCHAR(16), 
	zip_code VARCHAR(16), 
	timezone VARCHAR(64), 
	chain_domain VARCHAR(120), 
	departments JSON NOT NULL, 
	created_at DATETIME NOT NULL, 
	updated_at DATETIME NOT NULL, 
	CONSTRAINT pk_stores PRIMARY KEY (id), 
	CONSTRAINT uq_stores_location_id UNIQUE (location_id)
);
INSERT INTO "stores" VALUES('00000000-0000-7000-8000-000000000101','99999001','SAMPLE MARKET','Sample Market Downtown','100 Sample Street',NULL,'Sampleton','ST','00001','America/New_York',NULL,'["Produce","Bakery","Deli"]','2026-10-06 12:10:00','2026-10-06 12:10:00');
CREATE INDEX ix_items_product_id ON items (product_id);
CREATE INDEX ix_kroger_product_cache_expires_at ON kroger_product_cache (expires_at);
CREATE INDEX ix_store_sections_store_id ON store_sections (store_id);
CREATE INDEX ix_dish_items_dish_id ON dish_items (dish_id);
CREATE INDEX ix_dish_items_item_id ON dish_items (item_id);
COMMIT;
