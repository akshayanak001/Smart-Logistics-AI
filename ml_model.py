import pandas as pd
import joblib
from sklearn.compose import ColumnTransformer
from sklearn.ensemble import RandomForestRegressor
from sklearn.metrics import mean_absolute_error
from sklearn.model_selection import train_test_split
from sklearn.pipeline import Pipeline
from sklearn.preprocessing import OneHotEncoder

DATASET_FILE = "ml_dataset.csv"
MODEL_FILE = "route_risk_model.pkl"


df = pd.read_csv(DATASET_FILE)

features = [
    "distance",
    "traffic",
    "weather_risk",
    "road_risk",
    "vehicle_risk",
    "package_weight",
    "priority",
]
target = "risk_score"

X = df[features]
y = df[target]

categorical_features = [
    "traffic",
    "weather_risk",
    "road_risk",
    "vehicle_risk",
    "priority",
]
numeric_features = [
    "distance",
    "package_weight",
]

preprocessor = ColumnTransformer(
    transformers=[
        ("categorical", OneHotEncoder(handle_unknown="ignore"), categorical_features),
        ("numeric", "passthrough", numeric_features),
    ]
)

model = RandomForestRegressor(
    n_estimators=150,
    random_state=42,
    max_depth=8,
)

pipeline = Pipeline([
    ("preprocessor", preprocessor),
    ("model", model),
])

X_train, X_test, y_train, y_test = train_test_split(
    X, y, test_size=0.20, random_state=42
)

pipeline.fit(X_train, y_train)
predictions = pipeline.predict(X_test)
mae = mean_absolute_error(y_test, predictions)

joblib.dump(pipeline, MODEL_FILE)

print("SMART LOGISTICS AI - ML TRAINING")
print("Training Random Forest model...")
print("Model Training Completed")
print(f"Mean Absolute Error: {mae:.2f}")
print(f"Model saved successfully as: {MODEL_FILE}")
print("ML MODEL READY")
