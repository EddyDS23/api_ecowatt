--Aqui crearemos usuario y base de datos

CREATE USER ecowatt_user WITH PASSWORD '12345678';

CREATE DATABASE ecowatt OWNER ecowatt_user;

GRANT ALL PRIVILEGES ON DATABASE ecowatt TO ecowatt_user


