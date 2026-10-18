from flask import Flask, render_template, request
import sqlite3
import joblib
import requests
import pandas as pd

from database import (
    initialize_database,
    save_route_analysis,
    save_accessibility_analysis,
)

app = Flask(__name__)

initialize_database()

MODEL_FILE = "route_risk_model.pkl"
ml_model = joblib.load(MODEL_FILE)

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
OSRM_URL = "https://router.project-osrm.org/route/v1/driving"
API_HEADERS = {
    "User-Agent": "Smart-Logistics-AI/1.0 (educational final-year project)"
}


@app.route("/")
def home():
    return render_template("index.html")


@app.route("/route-analysis")
def route_analysis():
    return render_template("route_analysis.html")


@app.route("/accessibility")
def accessibility():
    return render_template("accessibility.html")


@app.route("/analytics")
def analytics():
    connection = sqlite3.connect("smart_logistics.db")
    cursor = connection.cursor()

    total_routes = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses"
    ).fetchone()[0]

    total_accessibility = cursor.execute(
        "SELECT COUNT(*) FROM accessibility_analyses"
    ).fetchone()[0]

    average_risk = cursor.execute(
        "SELECT AVG(overall_risk) FROM route_analyses"
    ).fetchone()[0] or 0

    low_risk = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses WHERE risk_level='Low'"
    ).fetchone()[0]
    medium_risk = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses WHERE risk_level='Medium'"
    ).fetchone()[0]
    high_risk = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses WHERE risk_level='High'"
    ).fetchone()[0]

    average_accessibility = cursor.execute(
        "SELECT AVG(accessibility_score) FROM accessibility_analyses"
    ).fetchone()[0] or 0

    low_weather = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses WHERE weather_risk='Low'"
    ).fetchone()[0]
    medium_weather = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses WHERE weather_risk='Medium'"
    ).fetchone()[0]
    high_weather = cursor.execute(
        "SELECT COUNT(*) FROM route_analyses WHERE weather_risk='High'"
    ).fetchone()[0]

    connection.close()

    return render_template(
        "analytics.html",
        total_routes=total_routes,
        total_accessibility=total_accessibility,
        average_risk=round(average_risk),
        average_accessibility=round(average_accessibility),
        low_risk=low_risk,
        medium_risk=medium_risk,
        high_risk=high_risk,
        low_weather=low_weather,
        medium_weather=medium_weather,
        high_weather=high_weather,
    )


def geocode_location(location):
    """Convert a user-entered place/address into real coordinates."""
    location = (location or "").strip()
    if not location:
        return None

    response = requests.get(
        NOMINATIM_URL,
        params={
            "q": location,
            "format": "jsonv2",
            "limit": 1,
            "countrycodes": "in",
        },
        headers=API_HEADERS,
        timeout=15,
    )
    response.raise_for_status()
    data = response.json()

    if not data:
        return None

    return {
        "lat": float(data[0]["lat"]),
        "lon": float(data[0]["lon"]),
        "display_name": data[0].get("display_name", location),
    }


def format_duration(seconds):
    total_minutes = max(1, round(float(seconds) / 60))
    hours = total_minutes // 60
    minutes = total_minutes % 60
    return f"{hours}h {minutes}m" if hours else f"{minutes}m"


def get_real_route(start_location, destination):
    """Get actual road distance, travel time and route geometry from OSRM."""
    try:
        start = geocode_location(start_location)
        end = geocode_location(destination)

        if not start:
            return {"error": f"Could not find the starting location: {start_location}"}
        if not end:
            return {"error": f"Could not find the destination: {destination}"}

        route_url = (
            f"{OSRM_URL}/"
            f"{start['lon']},{start['lat']};"
            f"{end['lon']},{end['lat']}"
        )

        response = requests.get(
            route_url,
            params={
                "overview": "full",
                "geometries": "geojson",
                "alternatives": "true",
                "steps": "false",
            },
            headers=API_HEADERS,
            timeout=30,
        )
        response.raise_for_status()
        data = response.json()

        if data.get("code") != "Ok":
            return {"error": "The road-routing service could not calculate a route."}

        routes = []
        for index, route in enumerate(data.get("routes", [])):
            duration = float(route["duration"])
            routes.append(
                {
                    "id": index + 1,
                    "name": "Primary Route" if index == 0 else f"Alternative Route {index}",
                    "type": "Primary" if index == 0 else "Alternative",
                    "distance": round(route["distance"] / 1000, 2),
                    "time": format_duration(duration),
                    "duration_seconds": duration,
                    "geometry": route.get("geometry"),
                }
            )

        if not routes:
            return {"error": "No drivable road route was returned."}

        primary = routes[0]
        return {
            "distance": primary["distance"],
            "travel_time": primary["time"],
            "duration_seconds": primary["duration_seconds"],
            "geometry": primary["geometry"],
            "routes": routes,
            "start_coordinates": [start["lat"], start["lon"]],
            "destination_coordinates": [end["lat"], end["lon"]],
            "start_display_name": start["display_name"],
            "destination_display_name": end["display_name"],
        }

    except requests.RequestException as exc:
        print("Routing service error:", exc)
        return {"error": "Unable to contact the routing service. Check your internet connection and try again."}
    except Exception as exc:
        print("Route processing error:", exc)
        return {"error": "An unexpected error occurred while calculating the route."}


def analyze_traffic(preferred_time, priority):
    if priority == "Urgent":
        return "High"

    if preferred_time:
        try:
            hour = int(preferred_time.split(":")[0])
            if 7 <= hour <= 10 or 17 <= hour <= 20:
                return "High"
        except (ValueError, IndexError):
            pass

    return "Moderate"


def analyze_weather(delivery_date):
    try:
        day = int(delivery_date.split("-")[2])
    except (ValueError, IndexError):
        day = 1

    if day % 5 == 0:
        return "Heavy Rain", "High"
    if day % 3 == 0:
        return "Light Rain", "Medium"
    return "Partly Cloudy", "Low"


def analyze_road_condition(distance):
    if distance > 300:
        return "Medium"
    return "Low"


def analyze_vehicle_risk(vehicle_type, package_weight):
    try:
        weight = float(package_weight)
    except (TypeError, ValueError):
        weight = 0

    if vehicle_type == "Bike" and weight > 20:
        return "High"
    if vehicle_type == "Delivery Van" and weight > 500:
        return "Medium"
    if vehicle_type == "Truck" and weight > 2000:
        return "Medium"
    return "Low"


def calculate_risk_score(traffic, weather_risk, road_risk, vehicle_risk, priority):
    values = {"Low": 20, "Medium": 50, "High": 80}
    priority_values = {"Normal": 0, "High": 8, "Urgent": 15}

    score = (
        values.get(traffic, 20) * 0.25
        + values.get(weather_risk, 20) * 0.30
        + values.get(road_risk, 20) * 0.20
        + values.get(vehicle_risk, 20) * 0.15
        + priority_values.get(priority, 0) * 0.10
    )
    score = round(score)

    if score <= 35:
        level = "Low"
    elif score <= 65:
        level = "Medium"
    else:
        level = "High"
    return score, level


def predict_ml_risk(distance, traffic, weather_risk, road_risk, vehicle_risk, package_weight, priority):
    try:
        weight = float(package_weight)
    except (TypeError, ValueError):
        weight = 0

    input_data = pd.DataFrame(
        {
            "distance": [distance],
            "traffic": [traffic],
            "weather_risk": [weather_risk],
            "road_risk": [road_risk],
            "vehicle_risk": [vehicle_risk],
            "package_weight": [weight],
            "priority": [priority],
        }
    )

    prediction = round(float(ml_model.predict(input_data)[0]))
    prediction = max(0, min(100, prediction))

    if prediction <= 35:
        level = "Low"
    elif prediction <= 65:
        level = "Medium"
    else:
        level = "High"

    return prediction, level


@app.route("/analyze-route", methods=["POST"])
def analyze_route():
    start_location = request.form.get("start_location", "").strip()
    destination = request.form.get("destination", "").strip()
    goods_type = request.form.get("goods_type", "").strip()
    package_weight = request.form.get("package_weight", "0").strip()
    vehicle_type = request.form.get("vehicle_type", "").strip()
    delivery_date = request.form.get("delivery_date", "").strip()
    preferred_time = request.form.get("preferred_time", "").strip()
    priority = request.form.get("priority", "Normal")
    route_preference = request.form.get("route_preference", "Balanced Recommendation")

    if not start_location or not destination:
        return render_template(
            "route_analysis.html",
            error="Please enter both starting location and destination.",
        ), 400

    route_data = get_real_route(start_location, destination)
    if route_data.get("error"):
        return render_template("route_analysis.html", error=route_data["error"]), 503

    distance = route_data["distance"]
    travel_time = route_data["travel_time"]
    actual_routes = route_data["routes"]

    traffic = analyze_traffic(preferred_time, priority)
    weather, weather_risk = analyze_weather(delivery_date)
    road_risk = analyze_road_condition(distance)
    vehicle_risk = analyze_vehicle_risk(vehicle_type, package_weight)

    overall_risk, risk_level = calculate_risk_score(
        traffic, weather_risk, road_risk, vehicle_risk, priority
    )
    ml_risk_score, ml_risk_level = predict_ml_risk(
        distance,
        traffic,
        weather_risk,
        road_risk,
        vehicle_risk,
        package_weight,
        priority,
    )

    route_options = []
    for index, actual_route in enumerate(actual_routes):
        route_copy = dict(actual_route)
        route_risk_score = overall_risk if index == 0 else max(0, min(100, overall_risk + index * 3))
        route_copy["risk"] = route_risk_score
        if route_risk_score <= 35:
            route_copy["risk_level"] = "Low"
        elif route_risk_score <= 65:
            route_copy["risk_level"] = "Medium"
        else:
            route_copy["risk_level"] = "High"
        route_options.append(route_copy)

    if route_preference == "Shortest Distance":
        recommended_route = min(route_options, key=lambda route: route["distance"])
        recommendation = "The shortest route returned by the road-routing service is recommended because the selected preference prioritizes minimum road distance."
    elif route_preference == "Fastest Delivery":
        recommended_route = min(route_options, key=lambda route: route["duration_seconds"])
        recommendation = "The fastest route returned by the road-routing service is recommended because the selected preference prioritizes travel time."
    elif route_preference == "Safer Route":
        recommended_route = min(route_options, key=lambda route: route["risk"])
        recommendation = "The route with the lowest calculated route-risk score among the routes returned by the routing service is recommended."
    else:
        min_distance = min(route["distance"] for route in route_options)
        max_distance = max(route["distance"] for route in route_options)
        min_time = min(route["duration_seconds"] for route in route_options)
        max_time = max(route["duration_seconds"] for route in route_options)

        def balanced_score(route):
            distance_component = 0 if max_distance == min_distance else (route["distance"] - min_distance) / (max_distance - min_distance)
            time_component = 0 if max_time == min_time else (route["duration_seconds"] - min_time) / (max_time - min_time)
            return distance_component * 0.30 + time_component * 0.30 + (route["risk"] / 100) * 0.40

        recommended_route = min(route_options, key=balanced_score)
        recommendation = "The balanced recommendation considers actual road distance, actual routing-service travel time and calculated route-risk score."

    result = {
        "start_location": start_location,
        "destination": destination,
        "goods_type": goods_type,
        "package_weight": package_weight,
        "vehicle_type": vehicle_type,
        "delivery_date": delivery_date,
        "preferred_time": preferred_time,
        "priority": priority,
        "route_preference": route_preference,
        "distance": distance,
        "travel_time": travel_time,
        "time": travel_time,
        "duration_seconds": route_data["duration_seconds"],
        "geometry": route_data["geometry"],
        "start_coordinates": route_data["start_coordinates"],
        "destination_coordinates": route_data["destination_coordinates"],
        "start_display_name": route_data["start_display_name"],
        "destination_display_name": route_data["destination_display_name"],
        "traffic": traffic,
        "weather": weather,
        "weather_risk": weather_risk,
        "road_risk": road_risk,
        "vehicle_risk": vehicle_risk,
        "overall_risk": overall_risk,
        "risk_level": risk_level,
        "ml_risk_score": ml_risk_score,
        "ml_risk_level": ml_risk_level,
        "route_options": route_options,
        "recommended_route": recommended_route,
        "recommendation": recommendation,
        "route_source": "OpenStreetMap Nominatim + OSRM",
        "traffic_note": "Traffic level is a project intelligence estimate based on selected delivery time and priority; it is not live traffic data.",
    }

    save_route_analysis(result)
    return render_template("results.html", result=result)


@app.route("/analyze-accessibility", methods=["POST"])
def analyze_accessibility():
    location = request.form.get("location", "").strip()
    user_type = request.form.get("user_type", "").strip()
    distance_range = request.form.get("distance_range", "").strip()

    ramp_score = 82
    pathway_score = 75
    facility_score = 79
    signage_score = 70
    score = round((ramp_score + pathway_score + facility_score + signage_score) / 4)

    if score >= 80:
        level = "Highly Accessible"
        recommendation = "The selected location shows good overall accessibility with reasonable access to pathways, facilities and mobility-support features."
    elif score >= 60:
        level = "Moderately Accessible"
        recommendation = "The location provides moderate accessibility. Improving pathways, signage and mobility facilities could provide a better experience."
    else:
        level = "Needs Improvement"
        recommendation = "The location may require accessibility improvements, particularly in mobility access, pathways and supporting facilities."

    result = {
        "location": location,
        "user_type": user_type,
        "distance_range": distance_range,
        "score": score,
        "level": level,
        "ramp_score": ramp_score,
        "pathway_score": pathway_score,
        "facility_score": facility_score,
        "signage_score": signage_score,
        "recommendation": recommendation,
    }

    save_accessibility_analysis(result)
    return render_template("accessibility_result.html", result=result)


if __name__ == "__main__":
    app.run(debug=True, use_reloader=False)
