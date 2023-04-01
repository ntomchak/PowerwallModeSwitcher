import logging
import os
import pypowerwall
import yaml
import time
import datetime
import json

def pct_api_to_app(api):
    return (api - 0.05) / 0.95

def pct_app_to_api(app):
    return (app * 0.95) + 0.05
    
def log_and_print(log):
    print(log)
    logging.info(log)

now = datetime.datetime.now()


# LOAD CONFIGURATION ---------------------------
dir_name = os.path.dirname(__file__)
config_file_name = os.path.join(dir_name, "solarforecast-config.yml")
config_file = open(config_file_name, 'r')
config = yaml.safe_load(config_file.read())
config_file.close()


auth_config = config["auth"]
host = auth_config["host"]
email = auth_config["email"]
password = auth_config["password"]
timezone = auth_config["timezone"]




if now.weekday() < 5:
    weekend_or_weekday = "weekday"
else:
    weekend_or_weekday = "weekend"
upper_pp_above_reserve = config["predictions"]["sunrise_to_nine"][weekend_or_weekday]["upper_pp_above_reserve"] / 100.0
lower_pp_above_reserve = config["predictions"]["sunrise_to_nine"][weekend_or_weekday]["lower_pp_above_reserve"] / 100.0
before_nine_kwh_per_hour = config["predictions"]["sunrise_to_nine"][weekend_or_weekday]["kwh_per_hour"]
before_nine_demand_multiplier = config["predictions"]["sunrise_to_nine"][weekend_or_weekday]["demand_multiplier"]
nine_to_four_kwh_per_hour = config["predictions"]["nine_to_four"][weekend_or_weekday]["kwh_per_hour"]
nine_to_four_lower_demand_multiplier = config["predictions"]["nine_to_four"][weekend_or_weekday]["lower_demand_multiplier"]
nine_to_four_upper_demand_multiplier = config["predictions"]["nine_to_four"][weekend_or_weekday]["upper_demand_multiplier"]

battery_capacity_kwh = config['predictions']['kwh_capacity']

log_folder = config["files"]["logs_folder"]
nine_to_four_energy_file_name = config["files"]["nine_to_four_energy_file"]

time_command = config["commands"]["time_command"]
self_command = config["commands"]["self_command"]
#-------------------------------------

nine_to_four_energy_file = open(nine_to_four_energy_file_name, 'r')
forecasted_nine_to_four_pv_energy = int(nine_to_four_energy_file.read()) / 1000.0
nine_to_four_energy_file.close()


pw = pypowerwall.Powerwall(host, password, email, timezone)
level = pct_api_to_app(pw.level() / 100)


# "self_consumption" or "autonomous" (time based)
operation_data = json.loads(pw.poll("/api/operation"))
mode = operation_data["real_mode"]
backup_reserve_percent = pct_api_to_app(operation_data["backup_reserve_percent"] / 100.0)

nine_am = datetime.datetime(now.year, now.month, now.day, 9, 0, 0, 0, now.tzinfo).timestamp()
hours_until_nine = (nine_am - now.timestamp()) / 3600.0
# proportion of battery
forecasted_demand_before_nine = (before_nine_kwh_per_hour * hours_until_nine) / battery_capacity_kwh
# proportion of battery
forecasted_battery_at_nine = level - forecasted_demand_before_nine

# kwh
forecasted_nine_to_four_battery_charging_demand = (1.0 - forecasted_battery_at_nine) * battery_capacity_kwh
forecasted_nine_to_four_home_demand = 7.0 * nine_to_four_kwh_per_hour
# kwh
forecasted_nine_to_four_total_demand = forecasted_nine_to_four_home_demand + forecasted_nine_to_four_battery_charging_demand


distance_to_upper_pp_above_reserve = level - (backup_reserve_percent + upper_pp_above_reserve)
before_nine_proportion_of_forecasted_demand_met_before_hitting_upper_pp_above_reserve = distance_to_upper_pp_above_reserve / forecasted_demand_before_nine

nine_to_four_proportion_of_forecasted_demand_met = forecasted_nine_to_four_pv_energy / forecasted_nine_to_four_total_demand

log = now.strftime("%H:%M:%S -------\n")
log += "battery: {batt:.3f},  rsrv threshold: {reserve:.3f},  FC demand <9: {before9:.4f},  FC batt @9: {batt9:.4f},  <9 proportion met: {before9prop:.2f},  9-4 batt demand: {battdemand94:2.2f}kWh,  9-4 home demand: {home94:2.2f}kWh,  9-4 tot demand: {dem94:2.2f}kWh,  9-4 pv FC: {pv94:2.2f}kWh,  9-4 proportion met: {prop94:2.2f},  mode: ".format(batt = level, reserve = backup_reserve_percent, before9 = forecasted_demand_before_nine, batt9 = forecasted_battery_at_nine, before9prop = before_nine_proportion_of_forecasted_demand_met_before_hitting_upper_pp_above_reserve, battdemand94 = forecasted_nine_to_four_battery_charging_demand, home94 = forecasted_nine_to_four_home_demand, dem94 = forecasted_nine_to_four_total_demand, pv94 = forecasted_nine_to_four_pv_energy, prop94 = nine_to_four_proportion_of_forecasted_demand_met) + mode + ",  weekend/weekday?: " + weekend_or_weekday

if mode == 'self_consumption':
    if before_nine_proportion_of_forecasted_demand_met_before_hitting_upper_pp_above_reserve > before_nine_demand_multiplier and nine_to_four_proportion_of_forecasted_demand_met > nine_to_four_upper_demand_multiplier:
        stream = os.popen(time_command)
        log += ("\n" + stream.read() + "--------------------------")
elif mode == 'autonomous':
    if level - backup_reserve_percent < lower_pp_above_reserve or nine_to_four_proportion_of_forecasted_demand_met < nine_to_four_lower_demand_multiplier:
        stream = os.popen(self_command)
        log += ("\n" + stream.read() + "--------------------------")
        
filename = now.strftime(log_folder + "%Y.%m.%d") + '.log'
logging.basicConfig(filename=filename, filemode = 'a', encoding='utf-8', level=logging.DEBUG)
log_and_print(log)
