CREATE TABLE tbPasswordResetTokens (
    prt_id SERIAL PRIMARY KEY,
    prt_user_id INT NOT NULL,
    prt_token VARCHAR(255) NOT NULL,
    prt_expires_at TIMESTAMP WITH TIME ZONE NOT NULL,
    prt_created_at TIMESTAMP WITH TIME ZONE DEFAULT NOW(),
    CONSTRAINT unique_reset_token UNIQUE(prt_token),
    CONSTRAINT fk_reset_token_user FOREIGN KEY(prt_user_id) REFERENCES tbUsers(user_id) ON DELETE CASCADE
);