import requests
import datetime
import logging
import yaml
import os


def log_and_print(log):
    print(log)
    logging.info(log)

# CONFIGURATION ---------------------------
dir_name = os.path.dirname(__file__)
config_file_name = os.path.join(dir_name, "solarforecast-config.yml")
config_file = open(config_file_name, 'r')
config = yaml.safe_load(config_file.read())
config_file.close()

log_folder = config["files"]["logs_folder"]
nine_to_four_energy_file = config["files"]["nine_to_four_energy_file"]
#-------------------------------------


now = datetime.datetime.now()
filename = now.strftime(log_folder + "%Y.%m.%d") + '.log'
logging.basicConfig(filename=filename, filemode = 'a', encoding='utf-8', level=logging.DEBUG)

response = requests.get('https://api.forecast.solar/estimate/20.74/-156.45/55/-30/5.95?time=seconds&horizon=15', headers={"Accept":"application/json"})
forecast = response.json()

# extract today's forecast for total watt-hours generated
beginning_of_today = datetime.datetime(now.year, now.month, now.day, 0, 0, 0, 0, now.tzinfo).timestamp()
day_watt_hours = forecast["result"]["watt_hours_day"][str(int(beginning_of_today))]
log_and_print("All day forecasted watt-hours: " + str(day_watt_hours))




# forecasted watt-hours generated after 9 am
nine = int(datetime.datetime(now.year, now.month, now.day, 9, 0, 0, 0, now.tzinfo).timestamp())
four = int(datetime.datetime(now.year, now.month, now.day, 16, 0, 0, 0, now.tzinfo).timestamp())

before_nine_watt_hours = 0
nine_to_four_watt_hours = 0

for timestamp, watt_hours in forecast["result"]["watt_hours_period"].items():
    if int(timestamp) > nine and int(timestamp) <= four:
        nine_to_four_watt_hours += watt_hours
    elif int(timestamp) <= nine:
        before_nine_watt_hours += watt_hours
log_and_print("9:00 to 16:00 forecasted watt-hours: " + str(nine_to_four_watt_hours))
log_and_print("Before 9:00 watt-hours: " + str(before_nine_watt_hours))
log_and_print("After 16:00 watt-hours: " + str(day_watt_hours - before_nine_watt_hours - nine_to_four_watt_hours))

with open(nine_to_four_energy_file, 'w') as file:
    file.write(str(nine_to_four_watt_hours))
