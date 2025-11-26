import string
import random
import json
import sys
import os


def resourcePath(relativePath: str) -> str:
    """ Get absolute path to resource, works for dev and for PyInstaller """
    try:
        basePath = sys._MEIPASS
    except Exception:
        basePath = os.environ.get("_MEIPASS2", os.path.abspath("."))

    return os.path.join(basePath, relativePath)


class Airport:
    def __init__(self, icao: str, altitude: int, config: str, facility: str):
        self.icao = icao
        self.altitude = altitude
        self.config = config
        self.facility = facility


class Controller:
    def __init__(self, airport_icao: str, facility: str, name: str, frequency: str):
        self.airport_icao = airport_icao
        self.facility = facility
        self.name = name
        self.frequency = frequency

    def __str__(self):
        return f"PSEUDOPILOT:{self.airport_icao}_M_{self.facility}\nCONTROLLER:{self.name}:{self.frequency}"


class Pilot:
    def __init__(self, cs: str, lat: str, long: str, alt: str, hdg: str, dep: str, sq: str,
                 rules: str, ac_type: str, crz: str, dest: str, rmk: str, rte: str,
                 pseudo_route: str, speed: str = "420", timeUntilSpawn: str = "0",
                 levelByFix: str = '', levelByLevel: str = "3000", owner: str = None):

        self.cs = cs
        self.lat = lat
        self.long = long
        self.alt = alt
        self.hdg = hdg
        self.dep = dep
        self.sq = sq
        self.rules = rules
        self.ac_type = ac_type
        self.crz = crz
        self.dest = dest
        self.rmk = rmk
        self.rte = rte
        self.pseudo_route = pseudo_route
        self.speed = speed
        self.timeUntilSpawn = timeUntilSpawn
        self.levelByFix = levelByFix
        self.levelByLevel = levelByLevel
        self.owner = owner if owner else self.dep

    def __str__(self):
        return (
            f"\nPSEUDOPILOT:{self.owner}_M_GND\n"
            f"@N:{self.cs}:{self.sq.rjust(4, '0')}:1:{self.lat}:{self.long}:{self.alt}:0:{self.hdg}:0\n"
            f"$FP{self.cs}:*A:{self.rules}:{self.ac_type}:{self.speed}:{self.dep}:0000::{self.crz}:{self.dest.strip()}:00:00:0:0::/{self.rmk}/:{self.rte.strip()}\n"
            f"SIMDATA:{self.cs}:*:*:25.1.0.000\n"
            f"$ROUTE:{self.pseudo_route}\n"
            f"START:{self.timeUntilSpawn}\n"
            f"DELAY:1:2\n"
            f"REQALT:{self.levelByFix}:{self.levelByLevel}\n"
            f"INITIALPSEUDOPILOT:{self.owner}_M_GND"
        )


class Scenario:
    def __init__(self, airport: Airport, app_data: str):
        self.airport = airport
        self.app_data = app_data
        self.controllers = []
        self.pilots = []

    def add_controller(self, controller: Controller):
        self.controllers.append(controller)

    def add_pilot(self, pilot: Pilot):
        self.pilots.append(pilot)

    def generate_scenario(self) -> str:
        scenario_file_str = (
            f"PSEUDOPILOT:ALL\n\nAIRPORT_ALT:{self.airport.altitude}\n\n{self.app_data}\n\n"
        )
        scenario_file_str += "".join(str(controller) + "\n" for controller in self.controllers)
        scenario_file_str += "\n".join(str(pilot) for pilot in self.pilots)
        return scenario_file_str


def generateSweatboxText(airport: Airport, app_data: str, vfrP: int, invalidRouteP: int,
                         invalidLevelP: int, fplanErrorsP: int, controllers: list[Controller],
                         autoPilots: int, manualPilots: list[Pilot], arrivalOffsets: list[str],
                         occupiedStands):

    scenario = Scenario(airport, app_data)

    for controller in controllers:
        scenario.add_controller(controller)

    pilots, occupiedStands = generate_random_plans(autoPilots, airport, vfrP,
                                                   invalidRouteP, invalidLevelP,
                                                   fplanErrorsP, occupiedStands)

    pilots += generate_arrival_plans(airport, arrivalOffsets)

    for pilot in pilots:
        scenario.add_pilot(pilot)

    for pilot in manualPilots:
        scenario.add_pilot(pilot)

    return scenario.generate_scenario(), occupiedStands


def generate_arrival_plans(arrival: Airport, offsets: list[str]) -> list[Pilot]:
    pilots = []
    with open(resourcePath("rsc/callsignsIFR.json")) as jsonData:
        JSONInjest = json.load(jsonData)
    callsigns = JSONInjest.get("callsigns")

    with open(resourcePath("rsc/aircraftTypes.json")) as jsonData:
        JSONInjest = json.load(jsonData)
    types = JSONInjest.get("callsigns")

    with open(resourcePath("rsc/arrivalRoutes.json")) as jsonData:
        arrivalRoutes = json.load(jsonData)

    for offset in offsets:
        chosenCallsign = random.choice(list(callsigns))
        cs = chosenCallsign + str(random.randint(10, 99)) + random.choice(
            string.ascii_uppercase) + random.choice(string.ascii_uppercase)

        actype = random.choice(types[chosenCallsign].split(","))
        lat = 25.273056
        long = 51.608056
        alt = 7000
        heading = int(((22 * 2.88) + 0.5)) << 2

        dest = arrival.icao
        rmk = "I"
        pseudoRoute = " ".join(arrivalRoutes.get(arrival.icao, []))

        rte = "ARRIVAL"

        pilot = Pilot(cs, lat, long, alt, heading, arrival.icao, "0000", "I",
                      actype, "38000", dest, rmk, rte, pseudoRoute,
                      "180", offset, "CF24", "2500", owner=arrival.icao)
        pilots.append(pilot)

    return pilots


def generate_random_plans(amount: int, dep: Airport, vfr_factor: int,
                          incorrect_factor: int, level_factor: int,
                          entry_error_factor: int, occupiedStands):

    numberOfVfr = int(amount * vfr_factor / 100)
    pilots = []

    stands = loadStand(dep.icao)

    with open(resourcePath("rsc/callsignsVFR.json")) as jsonData:
        JSONInjest = json.load(jsonData)
    callsigns = JSONInjest.get("callsigns")

    with open(resourcePath("rsc/vfrDestinations.json")) as jsonData:
        JSONInjest = json.load(jsonData)
    possDest = JSONInjest.get(dep.icao)

    current_sq = 0
    for _ in range(numberOfVfr):
        current_sq += 1
        cs = random.choice(list(callsigns))
        rules = "V"
        dest = random.choice(possDest)
        ac_type = random.choice(callsigns[cs].split(","))
        callsigns.pop(cs, None)

        stand = random.choice(list(stands))
        selectedStand = stands.get(stand)
        occupiedStands.append(stand)
        stands.pop(stand)

        lat, long, hdg = selectedStand["lat"], selectedStand["long"], \
            int(((int(selectedStand["hdg"]) * 2.88) + 0.5)) << 2

        sq = f"{current_sq:04}"
        crz = (500 * random.randint(1, 3)) + 1000
        rmk = "v"
        rte = "VFR"

        pilots.append(Pilot(cs, lat, long, dep.altitude, hdg,
                            dep.icao, sq, rules, ac_type, crz, dest, rmk, rte, ""))

    with open(resourcePath("rsc/callsignsIFR.json")) as jsonData:
        JSONInjest = json.load(jsonData)

    callsigns = JSONInjest.get(dep.icao)

    with open(resourcePath("rsc/aircraftTypes.json")) as jsonData:
        JSONInjest = json.load(jsonData)
    types = JSONInjest.get("callsigns")

    for _ in range(amount - numberOfVfr):
        current_sq += 1
        sq = f"{current_sq:04}"
        depAirport = dep.icao

        dest, rte, crz = get_route(depAirport, incorrect_factor)

        chosenCallsign, cs, rules = selectAirline(dest, callsigns)

        possTypes = types[chosenCallsign].split(",")
        acType = random.choice(possTypes)

        stand = random.choice(list(stands))
        selectedStand = stands.get(stand)
        occupiedStands.append(stand)
        stands.pop(stand)

        lat, long, hdg = selectedStand["lat"], selectedStand["long"], \
            int(((int(selectedStand["hdg"]) * 2.88) + 0.5)) << 2

        rmk = "I"

        pilots.append(Pilot(cs, lat, long, dep.altitude, hdg,
                            depAirport, sq, rules, acType, crz, dest, rmk, rte, ""))

    return pilots, occupiedStands


def get_route(departure: str, incorrect_factor: int):
    try:
        if random.randint(1, 100) <= incorrect_factor:
            with open(resourcePath("rsc/invalidRoutes.json")) as jsonData:
                JSONInjest = json.load(jsonData)
            routes = JSONInjest.get(departure)
            destination, route_options = random.choice(list(routes.items()))
            route_str = random.choice(list(route_options))
            parts = route_str.split(",")
            return destination, parts[0], parts[1]

        else:
            with open(resourcePath("rsc/routes.json")) as jsonData:
                JSONInjest = json.load(jsonData)
            routes = JSONInjest.get(departure)
            destination, route_str = random.choice(list(routes.items()))
            parts = route_str.split(",")
            return destination, parts[0], parts[1]

    except Exception:
        return departure, "DIRECT", "10000"


def selectAirline(dest: str, callsigns: dict):
    airlines = []
    for airline, destinations in callsigns.items():
        if dest in destinations.split(","):
            airlines.append(airline)

    chosenCallsign = random.choice(list(airlines))
    cs = chosenCallsign + str(random.randint(11, 99)) + random.choice(
        string.ascii_uppercase) + random.choice(string.ascii_uppercase)
    rules = "I"

    return chosenCallsign, cs, rules


def loadStand(icao: str) -> dict:
    with open(resourcePath("rsc/stands.json")) as jsonData:
        JSONInjest = json.load(jsonData)
    return JSONInjest.get(icao)


def loadStandNums(icao: str):
    stands = loadStand(icao)
    standNums = list(stands.keys())
    return standNums, stands


if __name__ == "__main__":
    airport = Airport("OTHH", 35, "34", "GND")
    app_data = "APPROACH DATA GOES HERE"

    controllers = [
        Controller("OTHH", "GND", "OTHH_GND", "121.800")
    ]

    autoPilots = 10
    manualPilots = []
    arrivalOffsets = ["0", "5", "10"]
    occupiedStands = []

    scenario_text, occupiedStands = generateSweatboxText(
        airport=airport,
        app_data=app_data,
        vfrP=20,
        invalidRouteP=10,
        invalidLevelP=10,
        fplanErrorsP=5,
        controllers=controllers,
        autoPilots=autoPilots,
        manualPilots=manualPilots,
        arrivalOffsets=arrivalOffsets,
        occupiedStands=occupiedStands,
    )

    output_path = "scenario.txt"
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(scenario_text)

    print(f"✅ Scenario written to {output_path}")
