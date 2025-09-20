CREATE TABLE tbUsers(
user_id SERIAL NOT NULL,
user_name VARCHAR(100) NOT NULL,
user_email VARCHAR(150) NOT NULL,
user_password VARCHAR(255) NOT NULL,
user_create TIMESTAMP DEFAULT NOW(),
CONSTRAINT pk_user_id PRIMARY KEY(user_id),
CONSTRAINT unique_user_email UNIQUE(user_email)
);

CREATE TABLE tbDevice(
dev_id SERIAL NOT NULL,
dev_user_id INT NOT NULL,
dev_brand VARCHAR(200) NOT NULL, --Marca
dev_model VARCHAR(200) NOT NULL,
dev_endpoint_url TEXT NOT NULL,
dev_installed TIMESTAMP DEFAULT NOW(),
dev_status BOOLEAN  DEFAULT true,
CONSTRAINT pk_dev_id PRIMARY KEY(dev_id),
CONSTRAINT fk_dev_user_id FOREIGN KEY(dev_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE -- Si se elimine el usuario sus dispositivos igual
);

CREATE TABLE tbReports(
rep_id SERIAL NOT NULL,
rep_user_id INT NOT NULL,
rep_total_kwh DECIMAL(10,2),
rep_estimated_cost DECIMAL(10,2),
rep_created TIMESTAMP DEFAULT NOW(),
CONSTRAINT pk_rep_id PRIMARY KEY(rep_id),
CONSTRAINT fk_dev_user_id FOREIGN KEY(rep_user_id) REFERENCES tbUsers(user_id)
);

