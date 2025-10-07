-- 1. Tabla de Usuarios (con día de facturación)
CREATE TABLE tbUsers(
    user_id SERIAL NOT NULL,
    user_name VARCHAR(100) NOT NULL,
    user_email VARCHAR(150) NOT NULL,
    user_password VARCHAR(255) NOT NULL,
    user_trf_rate VARCHAR(10) NOT NULL,
    user_billing_day INT NOT NULL DEFAULT 1, -- Día del mes para el corte (1-31)
    user_created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT pk_user_id PRIMARY KEY(user_id),
    CONSTRAINT unique_user_email UNIQUE(user_email)
);

-- 2. Tabla de Dispositivos (adaptada para el Shelly)
CREATE TABLE tbDevice(
    dev_id SERIAL NOT NULL,
    dev_user_id INT NOT NULL,
    dev_hardware_id VARCHAR(255) NOT NULL, -- La MAC Address del Shelly
    dev_name VARCHAR(100) NOT NULL,        -- Nombre que el usuario le da (ej: "Cocina")
    dev_brand VARCHAR(200) DEFAULT 'Shelly',
    dev_model VARCHAR(200) DEFAULT '1PM Gen4',
    dev_installed TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    dev_status BOOLEAN DEFAULT true,
    CONSTRAINT pk_dev_id PRIMARY KEY(dev_id),
    CONSTRAINT unique_hardware_id UNIQUE(dev_hardware_id),
    CONSTRAINT fk_dev_user_id FOREIGN KEY(dev_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);

-- 3. Tabla de Tarifas (Reestructurada para ser flexible)
CREATE TABLE tbTarrifs (
    trf_id SERIAL PRIMARY KEY,
    trf_rate_name VARCHAR(10) NOT NULL,
    trf_level_name VARCHAR(30) NOT NULL,
    trf_lower_limit_kwh INT NOT NULL,
    trf_upper_limit_kwh INT, -- Nulo para el último nivel (excedente)
    trf_price_per_kwh DECIMAL(10, 5) NOT NULL,
    trf_valid_from DATE NOT NULL,
    trf_valid_to DATE NOT NULL
);

-- 4. NUEVA: Tabla para Notificaciones Push (Alertas)
CREATE TABLE tbAlerts (
    ale_id SERIAL PRIMARY KEY,
    ale_user_id INT NOT NULL,
    ale_title VARCHAR(150) NOT NULL,
    ale_body TEXT NOT NULL,
    ale_is_read BOOLEAN DEFAULT FALSE,
    ale_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_alert_user FOREIGN KEY(ale_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);

-- 5. NUEVA: Tabla para Recomendaciones de la IA
CREATE TABLE tbRecommendations (
    rec_id SERIAL PRIMARY KEY,
    rec_user_id INT NOT NULL,
    rec_text TEXT NOT NULL,
    rec_is_read BOOLEAN DEFAULT FALSE,
    rec_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT fk_rec_user_id FOREIGN KEY(rec_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);

-- 6. NUEVA Y CRÍTICA: Tabla para Tokens de Refresco (Para mantener la sesión abierta)
CREATE TABLE tbRefreshTokens (
    ref_id SERIAL PRIMARY KEY,
    ref_user_id INT NOT NULL,
    ref_token VARCHAR(512) NOT NULL,
    ref_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    ref_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_refresh_token UNIQUE(ref_token),
    CONSTRAINT fk_refresh_user FOREIGN KEY(ref_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);

-- La tabla de reportes se puede mantener si quieres guardar historiales mensuales, pero los cálculos en tiempo real se harán con Redis.
CREATE TABLE tbReports(
    rep_id SERIAL NOT NULL,
    rep_user_id INT NOT NULL,
    rep_total_kwh DECIMAL(10,2),
    rep_estimated_cost DECIMAL(10,2),
    rep_created TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT pk_rep_id PRIMARY KEY(rep_id),
    CONSTRAINT fk_rep_user_id FOREIGN KEY(rep_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);

CREATE TABLE tbPasswordResetTokens (
    prt_id SERIAL PRIMARY KEY,
    prt_user_id INT NOT NULL,
    prt_token VARCHAR(255) NOT NULL,
    prt_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    prt_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_reset_token UNIQUE(prt_token),
    CONSTRAINT fk_reset_token_user FOREIGN KEY(prt_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);