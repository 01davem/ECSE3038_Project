from datetime import datetime, timedelta
from typing import Annotated, List, Optional
from fastapi import FastAPI, HTTPException, Response, status
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
import requests
import re
import motor.motor_asyncio
from dotenv import dotenv_values

config = dotenv_values(".env")

client = motor.motor_asyncio.AsyncIOMotorClient(config["MONGO_URL"])
db = client.ECSE3038_Project_Database

from fastapi.middleware.cors import CORSMiddleware

app = FastAPI()

origins = ["https://simple-smart-hub-client.netlify.app"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

PyObjectId = Annotated[str, Field(alias="_id")]

class Settings(BaseModel):
    id: Optional[PyObjectId] = Field(default=None)
    user_temp: Optional[float] = None
    user_light: Optional[str] = None
    light_duration: Optional[str] = None
    light_time_off: Optional[str] = None

class ReturnSettings(BaseModel):
    id: Optional[PyObjectId] = Field(default=None)
    user_temp: Optional[float] = None
    user_light: Optional[str] = None
    light_time_off: Optional[str] = None

regex = re.compile(r'((?P<hours>\d+?)h)?((?P<minutes>\d+?)m)?((?P<seconds>\d+?)s)?')

def parse_time(time_str):
    parts = regex.match(time_str)
    if not parts:
        return
    parts = parts.groupdict()
    time_params = {}
    for name, param in parts.items():
        if param:
            time_params[name] = int(param)
    return timedelta(**time_params)

def get_sunset_time():
    URL = "https://api.sunrisesunset.io/json?lat=17.97787&lng=-76.77339"
    country_data = requests.get(url=URL).json()
    sunset = country_data["results"]["sunset"]
    user_sunset = datetime.strptime(sunset, '%H:%M:%S')
    return user_sunset.strftime('%H:%M:%S')

@app.put("/settings", status_code=200)
async def create_setting(settings: Settings):
    settings_check = await db["settings"].find().to_list(1)

    if settings.user_light == "sunset":
        user_light = datetime.strptime(get_sunset_time(), "%H:%M:%S")
    else:
        user_light = datetime.strptime(settings.user_light, "%H:%M:%S")
    
    duration = parse_time(settings.light_duration)
    settings.light_time_off = (user_light + duration).strftime("%H:%M:%S")

    if len(settings_check) == 0:
        settings_info = settings.dict(exclude={"light_duration"})
        new_setting = await db["settings"].insert_one(settings_info)
        created_setting = await db["settings"].find_one({"_id": new_setting.inserted_id})
        return JSONResponse(status_code=201, content=ReturnSettings(**created_setting).dict())

    else:
        db["settings"].update_one(
            {"_id": settings_check[0]["_id"]},
            {"$set": settings.dict(exclude={"light_duration"})}
        )
        created_setting = await db["settings"].find_one({"_id": settings_check[0]["_id"]})
        return ReturnSettings(**created_setting)

class SensorData(BaseModel):
    id: Optional[PyObjectId] = Field(default=None)
    temperature: Optional[float] = None
    presence: Optional[bool] = None
    datetime: Optional[str] = None

@app.get("/graph")
async def get_temp_data(size: int = None):
    data = await db["data"].find().to_list(size)
    return List[SensorData].validate_python(data)

@app.post("/sensorData", status_code=201)
async def create_sensor_data(data: SensorData):
    current_time = datetime.now().strftime("%H:%M:%S")
    data_info = data.dict()
    data_info["datetime"] = current_time
    new_entry = await db["sensorData"].insert_one(data_info)
    created_entry = await db["sensorData"].find_one({"_id": new_entry.inserted_id})
    return SensorData(**created_entry)

@app.get("/sensorData", status_code=200)
async def turn_on_components():
    data = await db["sensorData"].find().to_list(999)
    last = len(data) - 1
    sensor_data = data[last]
    settings = await db["settings"].find().to_list(999)
    user_setting = settings[0]

    if sensor_data["presence"]:
        fanState = sensor_data["temperature"] >= user_setting["user_temp"]
        lightState = user_setting["user_light"] == sensor_data["datetime"]
        
        on_check = await db["data"].find_one({"datetime": user_setting["user_light"]})
        off_check = await db["data"].find_one({"datetime": user_setting["light_time_off"]})
    

