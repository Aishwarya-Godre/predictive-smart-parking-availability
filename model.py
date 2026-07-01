# ============================================================
# ParkEase Nanded — Combined ML Model
# Random Forest + CSV Pattern + Zone Default
# ============================================================

import pandas as pd
import numpy as np
import pickle, os
from datetime import datetime

try:
    from sklearn.ensemble import RandomForestRegressor
    from sklearn.preprocessing import LabelEncoder
    from sklearn.model_selection import train_test_split
    from sklearn.metrics import mean_absolute_error
    SKLEARN = True
except ImportError:
    SKLEARN = False
    # Mock LabelEncoder if not available to avoid NameError
    class LabelEncoder:
        def fit_transform(self, x): return x
        def transform(self, x): return x


class ParkEaseModel:

    def __init__(self):

        self.model = None
        self.le = LabelEncoder()
        self.trained = False
        self.records = 0
        self.accuracy = 0

        # ---------------- LOCATIONS ----------------

        self.LOCATIONS = {
            "shivaji chowk":
                {"name":"Shivaji Chowk Parking","lat":19.1592,"lng":77.3082,"total":120,"zone":"Central"},
            "rajwada":
                {"name":"Rajwada Complex","lat":19.1621,"lng":77.3115,"total":80,"zone":"East"},
            "vazirabad":
                {"name":"Vazirabad Parking","lat":19.1565,"lng":77.3198,"total":60,"zone":"West"},
            "naganath gate":
                {"name":"Naganath Gate","lat":19.1534,"lng":77.3041,"total":90,"zone":"South"},
            "old town":
                {"name":"Old Town Parking","lat":19.1610,"lng":77.3062,"total":50,"zone":"Heritage"},
            "cidco":
                {"name":"CIDCO Parking","lat":19.1488,"lng":77.3223,"total":150,"zone":"New Area"},
            "guru nanak chowk":
                {"name":"Guru Nanak Chowk","lat":19.1578,"lng":77.3131,"total":40,"zone":"Central"},
            "hazur sahib":
                {"name":"Hazur Sahib Parking","lat":19.1540,"lng":77.3168,"total":200,"zone":"Sacred"},
            "bus stand area":
                {"name":"Bus Stand Parking","lat":19.1455,"lng":77.3074,"total":100,"zone":"Transport Hub"},
            "nanded railway":
                {"name":"Railway Station Parking","lat":19.1512,"lng":77.3187,"total":75,"zone":"Transport Hub"},
            "nanded fort":
                {"name":"Nanded Fort Area","lat":19.1627,"lng":77.3278,"total":60,"zone":"Heritage"},
            "kasturba hospital":
                {"name":"Kasturba Hospital","lat":19.1555,"lng":77.3090,"total":45,"zone":"Medical"},
            "mata gujari garden":
                {"name":"Visava Garden","lat":19.1480,"lng":77.3180,"total":70,"zone":"Tourism"},
            "siddheshwar temple":
                {"name":"Siddheshwar Temple","lat":19.1420,"lng":77.3100,"total":50,"zone":"Sacred"},
            "hingoli gate":
                {"name":"Hingoli Gate Area","lat":19.1650,"lng":77.3150,"total":80,"zone":"Transit"},
            "taroda naka":
                {"name":"Taroda Naka","lat":19.1780,"lng":77.3050,"total":120,"zone":"North Entrance"},
            "workshop corner":
                {"name":"Workshop Corner","lat":19.1700,"lng":77.3200,"total":55,"zone":"Industrial"},
            "anand nagar":
                {"name":"Anand Nagar","lat":19.1850,"lng":77.3100,"total":40,"zone":"Residential"},
            "maltekdi road":
                {"name":"Maltekdi Road","lat":19.1500,"lng":77.3250,"total":60,"zone":"Central"},
            "iti corner":
                {"name":"ITI Corner","lat":19.1400,"lng":77.3050,"total":45,"zone":"Education"},
            "degloor naka":
                {"name":"Degloor Naka","lat":19.1450,"lng":77.3300,"total":90,"zone":"South Entrance"},
            "workad road":
                {"name":"Workad Road","lat":19.1720,"lng":77.3350,"total":35,"zone":"East Area"},
            "vishweshwar chowk":
                {"name":"Vishweshwar Chowk","lat":19.1585,"lng":77.3120,"total":50,"zone":"Market"},
            "mahaveer chowk":
                {"name":"Mahaveer Chowk","lat":19.1570,"lng":77.3180,"total":65,"zone":"Market"},
            "amrut nagar":
                {"name":"Amrut Nagar Area","lat":19.1900,"lng":77.3250,"total":55,"zone":"North Area"},
            "cidco colony":
                {"name":"Cidco Colony","lat":19.1420,"lng":77.3220,"total":110,"zone":"Residential"},
        }

        # -------- DEFAULT AVAILABILITY --------

        self.DEFAULTS = {
            "shivaji chowk":65, "rajwada":55, "vazirabad":70, "naganath gate":50, "old town":60,
            "cidco":75, "guru nanak chowk":80, "hazur sahib":40, "bus stand area":45,
            "nanded railway":35, "nanded fort":75, "kasturba hospital":45, "mata gujari garden":65,
            "siddheshwar temple":55, "hingoli gate":40, "taroda naka":60, "workshop corner":50,
            "anand nagar":80, "maltekdi road":65, "iti corner":70, "degloor naka":45,
            "workad road":75, "vishweshwar chowk":50, "mahaveer chowk":40, "amrut nagar":85,
            "cidco colony":65
        }

        self.pattern_data = {}


    # ============================================================
    # CSV TRAINING
    # ============================================================

    def train_from_csv(self, csv_path):

        if not os.path.exists(csv_path):
            print("CSV not found")
            return

        try:
            df = pd.read_csv(csv_path)
        except Exception as e:
            print(f"Error reading CSV: {e}")
            return

        # Normalize and map columns
        df.columns = [c.lower().strip() for c in df.columns]
        
        # Map known variations to required names (e.g. from nanded_parking_data.csv)
        col_map = {
            "location": "name", 
            "occupancy_rate_%": "occupancy",
            "occupationpct": "occupancy",
            "hour": "hour"
        }
        for src, dest in col_map.items():
            if src in df.columns and dest not in df.columns:
                df = df.rename(columns={src: dest})

        required = ["name","hour","occupancy"]

        for col in required:
            if col not in df.columns:
                print(f"DEBUG: Found columns in CSV: {list(df.columns)}")
                raise Exception(f"'{col}' column missing in CSV. Please ensure the CSV has 'name/location', 'hour', and 'occupancy/occupied_spots'.")

        df = df.dropna(subset=required)

        df["name_lower"] = df["name"].str.lower().str.strip()

        df["name_enc"] = self.le.fit_transform(df["name_lower"])

        df["avail_pct"] = 100 - df["occupancy"]

        X = df[["name_enc","hour"]]
        y = df["avail_pct"]

        if SKLEARN:

            X_train,X_test,y_train,y_test = train_test_split(
                X,y,test_size=0.2,random_state=42
            )

            self.model = RandomForestRegressor(
                n_estimators=100,
                max_depth=10,
                random_state=42
            )

            self.model.fit(X_train,y_train)

            pred = self.model.predict(X_test)

            mae = mean_absolute_error(y_test,pred)

            self.accuracy = round(100-mae,1)

            self.trained = True

        # build pattern fallback

        for _,row in df.iterrows():

            key = row["name_lower"]
            hour = int(row["hour"])
            occ = row["occupancy"]

            if key not in self.pattern_data:
                self.pattern_data[key] = {i:[] for i in range(24)}

            self.pattern_data[key][hour].append(occ)

        for k in self.pattern_data:
            for h in range(24):
                vals = self.pattern_data[k][h]
                self.pattern_data[k][h] = np.mean(vals) if vals else None

        # Add locations from CSV to LOCATIONS dictionary
        for loc in df["name"].unique():
            key = loc.lower().strip()
            if key not in self.LOCATIONS:
                # Add default metadata for new locations found in CSV
                self.LOCATIONS[key] = {
                    "name": loc.strip(),
                    "lat": 19.15 + (np.random.random() * 0.02 - 0.01),
                    "lng": 77.31 + (np.random.random() * 0.02 - 0.01),
                    "total": 100,
                    "zone": "General"
                }

        self.records = len(df)
        print(f"Training Complete. Loaded {len(self.LOCATIONS)} locations.")


    # ============================================================
    # SINGLE PREDICTION
    # ============================================================

    def predict(self,key,hour):

        hour = int(hour)

        # ML Prediction

        if self.trained:

            try:

                enc = self.le.transform([key])[0]

                pct = self.model.predict([[enc,hour]])[0]

                return np.clip(pct,0,100)

            except:
                pass

        # Pattern fallback

        if key in self.pattern_data:

            occ = self.pattern_data[key].get(hour)

            if occ is not None:
                return 100-occ

        # Default fallback

        base = self.DEFAULTS.get(key,60)

        if 8<=hour<=10 or 17<=hour<=19:
            base -= 20

        if 0<=hour<=5:
            base += 20

        return np.clip(base,0,100)


    # ============================================================
    # DASHBOARD PREDICTIONS
    # ============================================================

    def predict_all(self):

        hour = datetime.now().hour

        results = {}

        for key,loc in self.LOCATIONS.items():

            pct = self.predict(key,hour)

            avail = round(loc["total"] * pct / 100)

            results[key] = {

                "name":loc["name"],
                "lat":loc["lat"],
                "lng":loc["lng"],
                "total":loc["total"],
                "available":avail,
                "percentage":round(pct,1),
                "zone":loc["zone"]
            }

        return results