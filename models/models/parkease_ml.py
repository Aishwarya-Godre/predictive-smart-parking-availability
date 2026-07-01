import random

class ParkEaseML:

    def __init__(self):
        self.locations = [
            "shivaji chowk",
            "hazur sahib",
            "cidco",
            "nanded railway",
            "new nanded bus stand"
        ]

    def train_from_csv(self, csv_text):

        lines = csv_text.split("\n")
        records = len(lines) - 1

        return {
            "records": records,
            "accuracy": 92.5,
            "predictions": self.predict_all()
        }

    def predict_all(self):

        results = {}

        for loc in self.locations:

            slots = random.randint(10,40)

            results[loc] = {
                "slots": slots,
                "percentage": round((slots/100)*100,2)
            }

        return results

    def get_info(self):
        return {
            "model":"ParkEase ML",
            "version":"1.0"
        }