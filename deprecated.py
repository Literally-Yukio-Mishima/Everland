def writeToCSV(pFile, pLat, pLong, pAbove, pElevation):
    with open(pFile, 'a', newline='') as csvfile:
        writer = csv.writer(csvfile)

    # Write header if the file is empty
    if csvfile.tell() == 0:
        writer.writerow(['latitude', 'longitude', 'aboveSea', 'elevation'])

    writer.writerow([pLat, pLong, pAbove, pElevation])



def readCordinatedFromCSV(pFile):
    # Open the CSV file and iterate through it
    with open(pFile, 'r', newline='') as csvfile:
        reader = csv.reader(csvfile)
        last_line = None

        for row in reader:
            last_line = row  # Overwrite the last line until the end of the file

    print(row)
    return row[1], row[2]


def bruteforceCoordiantesToCSV(pFile, pSteps, pSleep=1):
    maxSteps = (180 / pSteps) * (360 / pSteps)
    index = 0

    lastLat, lastLon = readCordinatedFromCSV(pFile)
    if(lastLat == 90 and lastLon == 180):
        print("done.")
        return 0

    for i in range(-90, 90, pSteps): # latitude
        for j in range(-180, 180, pSteps): # longitude
            print(f"Status: {index} / {maxSteps} ({round(index/maxSteps*100, 3)}%)")

            elevation = bruteforceElevation(i, j)
            if(elevation == 0):
                above = True
            else:
                above = isStillAboveSeaLevelElevation(elevation)

            writeToCSV(pFile, i, j, above, elevation)
            index +=1

            time.sleep(pSleep)


def buildPartialGeoJson(pLong, pStep):
    df = pd.DataFrame(columns=['latitude', 'longitude', 'aboveSea', 'elevation'])

    index = 0
    print("\n\n lonfitude: " + pLong)
    for i in range(-90, 90, pStep): # latitude
        print(f"Status: {index} / {180/pStep} ({round(index/180/pStep*100, 3)}%) für lon = {pLong}")

        elevation = bruteforceElevation(i, pLong)
        if(elevation == 0):
            above = True
        else:
            above = isStillAboveSeaLevelElevation(elevation)

        df.loc[index] = [i, pLong, above, elevation]
        index +=1

    jsonData = df.to_json(orient='records')
    with open(f"./parts/bruteforcedCordinateLong{pLong}.geojson", 'w') as f:
        f.write(jsonData)


def buildGeoJson():
    step = 5
    for i in range(-180, 180, step):
        buildPartialGeoJson(i, step)
        time.sleep(10)


# Do not use
def getCountryCode(pCapital):
    url = f"https://restcountries.com/v3.1/capital/{pCapital}"
    response = requests.get(url)
    data = response.json()

    cca3 = data[0]['cca3']
    name = data[0]['name']['nativeName'][cca3.lower()]['common']

    return cca3, name



# Do not use
def getPopulationDensity(pCapital):
    cca3, country = getCountryCode(pCapital)
    url = f"https://stats.oecd.org/SDMX-JSON/data/POP_PROJ/{cca3}.MA+FE+TT.D199G5TT.VAR1/all?startTime=2020&endTime=2050&dimensionAtObservation=allDimensions"

    response = requests.get(url)
    data = response.json()

    population2020 = data['dataSets'][0]['observations']['0:2:0:0:0'][0]
    population2050 = data['dataSets'][0]['observations']['0:2:0:0:30'][0]

    print(f"Bevölkerung in {country} im Jahr 2020: {population2020}")
    print(f"Bevölkerung in Deutschland im Jahr 2050: {population2050}")
    print(f"Percsantage change: {calcPercentageIncrease(population2020, population2050)}%")




# Bruteforce coordinates with a scale of 10.
bruteforceCoordiantesToFile(10, 0)
# Plots the elevation data from the given file.
#plotDataFromFile('bruteforcedCordinateScale10.geojson')

# Plots the 10 biggest cities with population above 100000 people (using rain, wind, temp, sealevel)
#plotLivable(getCities(100000, 50))

# Plots the 10 biggest cities with population above 100000 people (using only sealevel)
#plotOnlySeaLevel(getCities(100000, 10))

# Checks the 10 biggest cities with population above 100000 people for liveability.
#checkCityForLivable(getCities(1000000, 5))
"""
ct = getCities(100, 5)
for index, city in ct.iterrows():
    above, _ = isStillAboveSeaLevelCordsMaps(ct['latitude'], ct['longitude'])
    print(f"City: {city['name']} is above sea level: {above}")
"""