BEGIN TRANSACTION;
CREATE TABLE alembic_version (
	version_num VARCHAR(32) NOT NULL, 
	CONSTRAINT alembic_version_pkc PRIMARY KEY (version_num)
);
INSERT INTO "alembic_version" VALUES('202610070207');
CREATE TABLE app_meta (
	id INTEGER NOT NULL, 
	auth_epoch INTEGER NOT NULL, 
	password_fp VARCHAR(64), 
	secret_key_check VARCHAR(64), 
	last_boot_version VARCHAR(32), 
	CONSTRAINT pk_app_meta PRIMARY KEY (id), 
	CONSTRAINT ck_app_meta_single_row CHECK (id = 1)
);
INSERT INTO "app_meta" VALUES(1,3,NULL,NULL,'0.4.0');
CREATE TABLE applied_ops (
	op_id VARCHAR(36) NOT NULL, 
	trip_id VARCHAR(36) NOT NULL, 
	kind VARCHAR(24) NOT NULL, 
	client_id VARCHAR(64) NOT NULL, 
	member_id VARCHAR(36), 
	client_ts BIGINT NOT NULL, 
	effective_ts BIGINT NOT NULL, 
	received_at DATETIME NOT NULL, 
	result VARCHAR(16) NOT NULL, 
	reason VARCHAR(32), 
	CONSTRAINT pk_applied_ops PRIMARY KEY (op_id), 
	CONSTRAINT fk_applied_ops_member_id_members FOREIGN KEY(member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_applied_ops_trip_id_trips FOREIGN KEY(trip_id) REFERENCES trips (id) ON DELETE CASCADE
);
INSERT INTO "applied_ops" VALUES('op-sample-0001','00000000-0000-7000-8000-000000000902','item.set_state','phone-sample','00000000-0000-7000-8000-000000000001',1791295300000,1791295300000,'2026-10-06 14:01:40','applied',NULL);
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
CREATE TABLE dish_pairings (
	main_id VARCHAR(36) NOT NULL, 
	side_id VARCHAR(36) NOT NULL, 
	times_chosen INTEGER NOT NULL, 
	last_chosen_at DATETIME, 
	pinned BOOLEAN NOT NULL, 
	hidden BOOLEAN NOT NULL, 
	CONSTRAINT pk_dish_pairings PRIMARY KEY (main_id, side_id), 
	CONSTRAINT fk_dish_pairings_main_id_dishes FOREIGN KEY(main_id) REFERENCES dishes (id) ON DELETE CASCADE, 
	CONSTRAINT fk_dish_pairings_side_id_dishes FOREIGN KEY(side_id) REFERENCES dishes (id) ON DELETE CASCADE
);
INSERT INTO "dish_pairings" VALUES('00000000-0000-7000-8000-000000000401','00000000-0000-7000-8000-000000000402',3,'2026-10-06 12:50:00',0,0);
INSERT INTO "dish_pairings" VALUES('00000000-0000-7000-8000-000000000403','00000000-0000-7000-8000-000000000402',0,NULL,1,0);
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
CREATE TABLE plan_extras (
	id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	item_id VARCHAR(36), 
	text VARCHAR(80), 
	quantity VARCHAR(32) NOT NULL, 
	note VARCHAR(200), 
	added_by_member_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	CONSTRAINT pk_plan_extras PRIMARY KEY (id), 
	CONSTRAINT ck_plan_extras_item_or_text CHECK ((item_id IS NULL) != (text IS NULL)), 
	CONSTRAINT fk_plan_extras_added_by_member_id_members FOREIGN KEY(added_by_member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_plan_extras_item_id_items FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_plan_extras_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
);
INSERT INTO "plan_extras" VALUES('00000000-0000-7000-8000-000000000801','00000000-0000-7000-8000-000000000602','00000000-0000-7000-8000-000000000302',NULL,'3/2','Ripe ones','00000000-0000-7000-8000-000000000001','2026-10-06 12:55:00',NULL);
INSERT INTO "plan_extras" VALUES('00000000-0000-7000-8000-000000000802','00000000-0000-7000-8000-000000000602',NULL,'Birthday candles','1',NULL,NULL,'2026-10-06 12:56:00','2026-10-06 13:31:00');
INSERT INTO "plan_extras" VALUES('00000000-0000-7000-8000-000000000803','00000000-0000-7000-8000-000000000601','00000000-0000-7000-8000-000000000303',NULL,'1',NULL,'00000000-0000-7000-8000-000000000001','2026-09-28 12:20:00',NULL);
CREATE TABLE plan_item_overrides (
	plan_id VARCHAR(36) NOT NULL, 
	item_id VARCHAR(36) NOT NULL, 
	have_it BOOLEAN, 
	qty_delta VARCHAR(32), 
	qty_delta_unit VARCHAR(8), 
	swap_product_id VARCHAR(16), 
	swap_upc VARCHAR(16), 
	swap_size_text VARCHAR(80), 
	swap_sold_by VARCHAR(8), 
	updated_at DATETIME NOT NULL, 
	CONSTRAINT pk_plan_item_overrides PRIMARY KEY (plan_id, item_id), 
	CONSTRAINT fk_plan_item_overrides_item_id_items FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE CASCADE, 
	CONSTRAINT fk_plan_item_overrides_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
);
INSERT INTO "plan_item_overrides" VALUES('00000000-0000-7000-8000-000000000602','00000000-0000-7000-8000-000000000303',1,NULL,NULL,NULL,NULL,NULL,NULL,'2026-10-06 13:00:00');
INSERT INTO "plan_item_overrides" VALUES('00000000-0000-7000-8000-000000000602','00000000-0000-7000-8000-000000000301',NULL,'1','package','0000000000099','0000000000099','2 lb','UNIT','2026-10-06 13:01:00');
CREATE TABLE plan_meal_sides (
	plan_meal_id VARCHAR(36) NOT NULL, 
	side_id VARCHAR(36) NOT NULL, 
	position INTEGER NOT NULL, 
	CONSTRAINT pk_plan_meal_sides PRIMARY KEY (plan_meal_id, side_id), 
	CONSTRAINT fk_plan_meal_sides_plan_meal_id_plan_meals FOREIGN KEY(plan_meal_id) REFERENCES plan_meals (id) ON DELETE CASCADE, 
	CONSTRAINT fk_plan_meal_sides_side_id_dishes FOREIGN KEY(side_id) REFERENCES dishes (id) ON DELETE RESTRICT
);
INSERT INTO "plan_meal_sides" VALUES('00000000-0000-7000-8000-000000000701','00000000-0000-7000-8000-000000000402',0);
CREATE TABLE plan_meals (
	id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36) NOT NULL, 
	main_id VARCHAR(36) NOT NULL, 
	day DATE, 
	occasion VARCHAR(16) NOT NULL, 
	scale VARCHAR(32) NOT NULL, 
	position INTEGER NOT NULL, 
	added_by_member_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	deleted_at DATETIME, 
	CONSTRAINT pk_plan_meals PRIMARY KEY (id), 
	CONSTRAINT fk_plan_meals_added_by_member_id_members FOREIGN KEY(added_by_member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_plan_meals_main_id_dishes FOREIGN KEY(main_id) REFERENCES dishes (id) ON DELETE RESTRICT, 
	CONSTRAINT fk_plan_meals_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE CASCADE
);
INSERT INTO "plan_meals" VALUES('00000000-0000-7000-8000-000000000701','00000000-0000-7000-8000-000000000602','00000000-0000-7000-8000-000000000401','2026-10-07','dinner','2',0,'00000000-0000-7000-8000-000000000001','2026-10-06 12:50:00',NULL);
INSERT INTO "plan_meals" VALUES('00000000-0000-7000-8000-000000000702','00000000-0000-7000-8000-000000000602','00000000-0000-7000-8000-000000000401',NULL,'dinner','1',1,'00000000-0000-7000-8000-000000000001','2026-10-06 12:51:00','2026-10-06 13:30:00');
INSERT INTO "plan_meals" VALUES('00000000-0000-7000-8000-000000000703','00000000-0000-7000-8000-000000000601','00000000-0000-7000-8000-000000000403',NULL,'lunch','1/2',0,NULL,'2026-09-28 12:10:00',NULL);
CREATE TABLE plans (
	id VARCHAR(36) NOT NULL, 
	status VARCHAR(16) NOT NULL, 
	started_at DATETIME NOT NULL, 
	archived_at DATETIME, 
	CONSTRAINT pk_plans PRIMARY KEY (id)
);
INSERT INTO "plans" VALUES('00000000-0000-7000-8000-000000000601','archived','2026-09-28 12:00:00','2026-10-05 12:00:00');
INSERT INTO "plans" VALUES('00000000-0000-7000-8000-000000000602','active','2026-10-05 12:00:00',NULL);
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
CREATE TABLE trip_items (
	id VARCHAR(36) NOT NULL, 
	trip_id VARCHAR(36) NOT NULL, 
	line_key VARCHAR(64) NOT NULL, 
	item_id VARCHAR(36), 
	name VARCHAR(80) NOT NULL, 
	product_id VARCHAR(16), 
	upc VARCHAR(16), 
	image_url VARCHAR(300), 
	product_url VARCHAR(300), 
	size_text VARCHAR(80), 
	qty_text VARCHAR(120) NOT NULL, 
	quantity VARCHAR(32) NOT NULL, 
	unit VARCHAR(8) NOT NULL, 
	unit_cents INTEGER, 
	line_cents INTEGER, 
	regular_cents INTEGER, 
	on_sale BOOLEAN NOT NULL, 
	sale_ends DATE, 
	section_key VARCHAR(64), 
	section_label VARCHAR(120), 
	section_order INTEGER NOT NULL, 
	aisle_side VARCHAR(1), 
	bay INTEGER NOT NULL, 
	used_by JSON NOT NULL, 
	warnings JSON NOT NULL, 
	position INTEGER NOT NULL, 
	state VARCHAR(8) NOT NULL, 
	state_ts BIGINT NOT NULL, 
	state_by_member_id VARCHAR(36), 
	note VARCHAR(200), 
	note_ts BIGINT NOT NULL, 
	note_by_member_id VARCHAR(36), 
	version INTEGER NOT NULL, 
	removed_at DATETIME, 
	CONSTRAINT pk_trip_items PRIMARY KEY (id), 
	CONSTRAINT fk_trip_items_item_id_items FOREIGN KEY(item_id) REFERENCES items (id) ON DELETE SET NULL, 
	CONSTRAINT fk_trip_items_note_by_member_id_members FOREIGN KEY(note_by_member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_trip_items_state_by_member_id_members FOREIGN KEY(state_by_member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_trip_items_trip_id_trips FOREIGN KEY(trip_id) REFERENCES trips (id) ON DELETE CASCADE
);
INSERT INTO "trip_items" VALUES('00000000-0000-7000-8000-000000000911','00000000-0000-7000-8000-000000000901','00000000-0000-7000-8000-000000000303','00000000-0000-7000-8000-000000000303','Cooking oil','0000000000003','0000000000003',NULL,NULL,'48 fl oz','1 package, 48 fl oz','1','package',899,899,899,0,NULL,NULL,NULL,9900,NULL,0,'[]','[]',0,'done',1790000000000,'00000000-0000-7000-8000-000000000001',NULL,0,NULL,2,NULL);
INSERT INTO "trip_items" VALUES('00000000-0000-7000-8000-000000000921','00000000-0000-7000-8000-000000000902','00000000-0000-7000-8000-000000000301','00000000-0000-7000-8000-000000000301','Ground beef','0000000000001','0000000000001','https://www.kroger.com/product/images/medium/front/0000000000001','https://www.example.com/p/sample-ground-beef/0000000000001','1 lb','2 packages, 1 lb each','2','package',499,998,1098,1,'2026-10-10','cat:meat-seafood','Meat & Seafood',9000,NULL,0,'[{"meal_id": "00000000-0000-7000-8000-000000000701", "name": "Tacos"}]','[]',0,'done',1791295300000,'00000000-0000-7000-8000-000000000001',NULL,0,NULL,3,NULL);
INSERT INTO "trip_items" VALUES('00000000-0000-7000-8000-000000000922','00000000-0000-7000-8000-000000000902','00000000-0000-7000-8000-000000000302','00000000-0000-7000-8000-000000000302','Bananas','0000000000002','0000000000002',NULL,NULL,NULL,'1 1/2 lb','3/2','pound',59,89,89,0,NULL,'cat:produce','Produce',100,NULL,0,'[]','["Low stock"]',1,'missed',1791295400000,NULL,'Ask at the counter',1791295400000,'00000000-0000-7000-8000-000000000001',5,NULL);
INSERT INTO "trip_items" VALUES('00000000-0000-7000-8000-000000000923','00000000-0000-7000-8000-000000000902','extra:candles',NULL,'Birthday candles',NULL,NULL,NULL,NULL,NULL,'1','1','each',NULL,NULL,NULL,0,NULL,'cat:other','Other',9900,NULL,0,'[]','[]',2,'todo',0,NULL,NULL,0,NULL,6,'2026-10-06 14:30:00');
CREATE TABLE trips (
	id VARCHAR(36) NOT NULL, 
	plan_id VARCHAR(36), 
	store_id VARCHAR(36), 
	status VARCHAR(16) NOT NULL, 
	status_ts BIGINT NOT NULL, 
	status_by_member_id VARCHAR(36), 
	created_by_member_id VARCHAR(36), 
	created_at DATETIME NOT NULL, 
	estimate_cents INTEGER NOT NULL, 
	savings_cents INTEGER NOT NULL, 
	not_priced INTEGER NOT NULL, 
	prices_as_of DATETIME, 
	actual_total_cents INTEGER, 
	finished_at DATETIME, 
	version INTEGER NOT NULL, 
	fingerprint VARCHAR(64) NOT NULL, 
	product_cache_expires_at DATETIME, 
	CONSTRAINT pk_trips PRIMARY KEY (id), 
	CONSTRAINT fk_trips_created_by_member_id_members FOREIGN KEY(created_by_member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_trips_plan_id_plans FOREIGN KEY(plan_id) REFERENCES plans (id) ON DELETE SET NULL, 
	CONSTRAINT fk_trips_status_by_member_id_members FOREIGN KEY(status_by_member_id) REFERENCES members (id) ON DELETE SET NULL, 
	CONSTRAINT fk_trips_store_id_stores FOREIGN KEY(store_id) REFERENCES stores (id) ON DELETE SET NULL
);
INSERT INTO "trips" VALUES('00000000-0000-7000-8000-000000000901','00000000-0000-7000-8000-000000000601','00000000-0000-7000-8000-000000000101','finished',1790000000000,'00000000-0000-7000-8000-000000000001','00000000-0000-7000-8000-000000000001','2026-09-29 15:00:00',1234,50,0,'2026-09-29 15:00:00',1199,'2026-09-29 16:00:00',4,'',NULL);
INSERT INTO "trips" VALUES('00000000-0000-7000-8000-000000000902','00000000-0000-7000-8000-000000000602','00000000-0000-7000-8000-000000000101','active',1791295200000,'00000000-0000-7000-8000-000000000001','00000000-0000-7000-8000-000000000001','2026-10-06 14:00:00',2096,0,1,'2026-10-06 14:00:00',NULL,NULL,7,'0f',NULL);
CREATE INDEX ix_items_product_id ON items (product_id);
CREATE INDEX ix_kroger_product_cache_expires_at ON kroger_product_cache (expires_at);
CREATE INDEX ix_store_sections_store_id ON store_sections (store_id);
CREATE INDEX ix_dish_items_dish_id ON dish_items (dish_id);
CREATE INDEX ix_dish_items_item_id ON dish_items (item_id);
CREATE INDEX ix_plan_extras_item_id ON plan_extras (item_id);
CREATE INDEX ix_plan_extras_plan_id ON plan_extras (plan_id);
CREATE INDEX ix_dish_pairings_side_id ON dish_pairings (side_id);
CREATE INDEX ix_plan_meals_main_id ON plan_meals (main_id);
CREATE INDEX ix_plan_meals_plan_id ON plan_meals (plan_id);
CREATE INDEX ix_plan_meal_sides_side_id ON plan_meal_sides (side_id);
CREATE INDEX ix_trips_plan_id ON trips (plan_id);
CREATE INDEX ix_trips_product_cache_expires_at ON trips (product_cache_expires_at);
CREATE INDEX ix_applied_ops_received_at ON applied_ops (received_at);
CREATE INDEX ix_applied_ops_trip_id ON applied_ops (trip_id);
CREATE INDEX ix_trip_items_trip_id ON trip_items (trip_id);
COMMIT;
