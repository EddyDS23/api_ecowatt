
CREATE TABLE tbTarrifs (
    trf_id SERIAL PRIMARY KEY,
    trf_rate_name VARCHAR(10) NOT NULL,
    trf_level_name VARCHAR(30) NOT NULL,
    trf_lower_limit_kwh INT NOT NULL,
    trf_upper_limit_kwh INT, -- Nulo para el último nivel (excedente)
    trf_price_per_kwh DECIMAL(10, 5) NOT NULL,
    trf_fixed_charge_mxn DECIMAL(10, 2) DEFAULT 0.00,
    trf_valid_from DATE NOT NULL,
    trf_valid_to DATE NOT NULL
);