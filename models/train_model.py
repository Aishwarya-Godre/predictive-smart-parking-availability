import pandas as pd
from sklearn.ensemble import RandomForestClassifier
import pickle
import os

# -------------------
# Ensure models folder exists
if not os.path.exists("models"):
    os.makedirs("models")
# -------------------

# Dummy dataset
data = {
    "hour": [9,10,11,12],
    "day": [0,1,2,3],
    "zone": ["A","B","C","A"],
    "availability": [1,0,1,0]
}
df = pd.DataFrame(data)

# Features & Target
X = df[["hour","day","zone"]]
X = pd.get_dummies(X)  # encode zone
y = df["availability"]

# Train Random Forest
model = RandomForestClassifier()
model.fit(X, y)

# Save trained model
pickle.dump(model, open("models/best_model.pkl", "wb"))

print("Model trained and saved in models/best_model.pkl")