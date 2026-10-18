import sqlite3

DATABASE_NAME = "smart_logistics.db"


def get_connection():
    connection = sqlite3.connect(DATABASE_NAME)
    connection.row_factory = sqlite3.Row
    return connection


def initialize_database():
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS route_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            start_location TEXT,
            destination TEXT,
            goods_type TEXT,
            package_weight REAL,
            vehicle_type TEXT,
            delivery_date TEXT,
            preferred_time TEXT,
            priority TEXT,
            route_preference TEXT,
            distance REAL,
            traffic TEXT,
            weather TEXT,
            weather_risk TEXT,
            road_risk TEXT,
            vehicle_risk TEXT,
            overall_risk INTEGER,
            risk_level TEXT,
            recommended_route TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS accessibility_analyses (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            location TEXT,
            user_type TEXT,
            distance_range TEXT,
            accessibility_score INTEGER,
            accessibility_level TEXT,
            ramp_score INTEGER,
            pathway_score INTEGER,
            facility_score INTEGER,
            signage_score INTEGER,
            recommendation TEXT,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    connection.commit()
    connection.close()


def save_route_analysis(result):
    connection = get_connection()
    cursor = connection.cursor()

    recommended_route = ""
    if result.get("recommended_route"):
        recommended_route = result["recommended_route"].get("name", "")

    cursor.execute("""
        INSERT INTO route_analyses (
            start_location, destination, goods_type, package_weight,
            vehicle_type, delivery_date, preferred_time, priority,
            route_preference, distance, traffic, weather, weather_risk,
            road_risk, vehicle_risk, overall_risk, risk_level,
            recommended_route
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result.get("start_location"),
        result.get("destination"),
        result.get("goods_type"),
        result.get("package_weight"),
        result.get("vehicle_type"),
        result.get("delivery_date"),
        result.get("preferred_time"),
        result.get("priority"),
        result.get("route_preference"),
        result.get("distance"),
        result.get("traffic"),
        result.get("weather"),
        result.get("weather_risk"),
        result.get("road_risk"),
        result.get("vehicle_risk"),
        result.get("overall_risk"),
        result.get("risk_level"),
        recommended_route,
    ))

    connection.commit()
    connection.close()


def save_accessibility_analysis(result):
    connection = get_connection()
    cursor = connection.cursor()

    cursor.execute("""
        INSERT INTO accessibility_analyses (
            location, user_type, distance_range, accessibility_score,
            accessibility_level, ramp_score, pathway_score, facility_score,
            signage_score, recommendation
        )
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    """, (
        result.get("location"),
        result.get("user_type"),
        result.get("distance_range"),
        result.get("score"),
        result.get("level"),
        result.get("ramp_score"),
        result.get("pathway_score"),
        result.get("facility_score"),
        result.get("signage_score"),
        result.get("recommendation"),
    ))

    connection.commit()
    connection.close()


if __name__ == "__main__":
    initialize_database()
    print("Smart Logistics AI database initialized successfully.")
