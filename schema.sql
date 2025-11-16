DROP TABLE IF EXISTS classes;
DROP TABLE IF EXISTS users;
DROP TABLE IF EXISTS bookings;

CREATE TABLE users (
    id TEXT PRIMARY KEY,
    username TEXT NOT NULL UNIQUE,
    password TEXT NOT NULL, 
    role TEXT NOT NULL DEFAULT 'user'
);

CREATE TABLE classes (
    id TEXT PRIMARY KEY,
    name TEXT NOT NULL,
    time TEXT NOT NULL,
    capacity INTEGER NOT NULL,
    price REAL NOT NULL, 
    trainer TEXT NOT NULL
);

CREATE TABLE bookings (
    id TEXT PRIMARY KEY,
    classId TEXT NOT NULL,
    userId TEXT NOT NULL,
    timestamp DATETIME DEFAULT CURRENT_TIMESTAMP,
    status TEXT NOT NULL DEFAULT 'pending',
    FOREIGN KEY (classId) REFERENCES classes (id) ON DELETE CASCADE,
    FOREIGN KEY (userId) REFERENCES users (id) ON DELETE CASCADE
);


INSERT INTO users (id, username, password, role) VALUES ('admin-123', 'admin', 'admin', 'admin');

-- New Trainer Accounts Added
INSERT INTO users (id, username, password, role) VALUES ('trainer-alex', 'alexsmith', 'trainerpass', 'trainer');
INSERT INTO users (id, username, password, role) VALUES ('trainer-maria', 'marialee', 'trainerpass', 'trainer');
INSERT INTO users (id, username, password, role) VALUES ('trainer-basti', 'basticruz', 'trainerpass', 'trainer');

INSERT INTO users (id, username, password, role) VALUES ('user-456', 'jhon', 'user123', 'user');

INSERT INTO classes (id, name, time, capacity, price, trainer) VALUES ('class-spin', 'Morning Spin', 'Mon, Wed @ 6:00 AM', 15, 600.00, 'Alex Smith');
INSERT INTO classes (id, name, time, capacity, price, trainer) VALUES ('class-yoga', 'Evening Yoga', 'Tue, Thu @ 7:00 PM', 20, 500.00, 'Maria Lee');
INSERT INTO classes (id, name, time, capacity, price, trainer) VALUES ('class-hiit', 'Lunchtime HIIT', 'Fri @ 12:00 PM', 10, 750.00, 'Basti Cruz');