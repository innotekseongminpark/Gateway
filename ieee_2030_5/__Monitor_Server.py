
import sys, os, time
from datetime import date, datetime, timedelta
import traceback
import math
from typing import Union
import traceback
import uvicorn
from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

import sqlite3
import pickle
import numpy as np
import pandas as pd
from peewee import *
from playhouse.shortcuts import model_to_dict
import re
import matplotlib.pyplot as plt
import matplotlib.dates as mdates
import matplotlib.ticker as ticker
import io, base64
#os.chdir("../")     # to py\gridappsd-2030_5-0.0.2a14

sys.path.append('./')
from ieee_2030_5.DB_Driver import *

LoadReadingsDB (conn_only=True)

app = FastAPI()
app.mount("/static", StaticFiles(directory="static"), name="static")
templates = Jinja2Templates(directory="templates")

def time2str (t):
    return time.strftime('%Y_%m_%d_%H_%M_%S', time.localtime(t))
templates.env.filters["time2str"] = time2str

@app.get("/", response_class=HTMLResponse)
def list_devices(request: Request):
    devices = Reading.select(Reading.device).distinct()
    print(f"Num of Devices : {len(devices)}")
    device_paths = sorted([(reading.device, f"{request.base_url}view?device={reading.device}") for reading in devices])
    print(device_paths)

    return templates.TemplateResponse(
        "list_devices.html", {"request": request, "device_paths": device_paths}
    )

def data_view_device (request, device, selected):
    model = Reading.select(Reading.timestamp).where(Reading.device == device)
    dev_df = pd.DataFrame(model.dicts())
    dev_df['date'] = dev_df['timestamp'].dt.strftime('%Y-%m-%d')
    selections = list(dev_df.groupby(dev_df['date']).groups.keys())
    selections = [(s, f"{request.base_url}view?device={device}&selected={s}") for s in selections]
    print (selections)
    if selected == None:
        date_on = datetime.strptime(selections[-1][0], '%Y-%m-%d').date()
    else:
        date_on = datetime.strptime(selected, '%Y-%m-%d').date()
    #date_on = datetime.strptime(selected, '%Y-%m-%d').date()

    date_next = date_on + timedelta(days=+1)
    selected = date_on.strftime('%Y-%m-%d')
    date_next_str = date_next.strftime('%Y-%m-%d')
    reading = Reading.select().where((Reading.device == device)
                                     & (Reading.timestamp.between(date_on, date_next)))
    df = pd.DataFrame(reading.dicts())
    if len(df) > 0:
        df.set_index('timestamp', inplace=True)
        sel_df = df.tail(1).reset_index()
        print(sel_df)

        print (f"-----day df  {device} {selected}")
        print (model_to_dict(Reading()))
        day_df = pd.DataFrame([model_to_dict(Reading())] * 48)
        print("1")
        day_df['timestamp'] = pd.date_range(selected, periods=48, freq='30T')
        print("2")
        day_df.set_index('timestamp', inplace=True)
        print("3")
        df = df.resample('30T').mean(numeric_only=True)
        print("4")
        df['device'] = device
        print("5")
        day_df.update(df)
        print("6")
        day_df.reset_index(inplace=True)
        print(day_df)
    else:
        sel_df = pd.DataFrame()
        day_df = pd.DataFrame()

    if 1:
        print(f"-----plot power  {len(sel_df)} {len(day_df)}")
        fig1, ax = plt.subplots(figsize=(5, 2))
        plt.title('Power', fontsize=12)
        ax.fill_between(day_df['timestamp'], 0., day_df['appr_pow'], alpha=1.0, label=f"Apparent Power")
        ax.fill_between(day_df['timestamp'], 0., day_df['real_pow'], alpha=0.6, label=f"Active Power")
        ax.fill_between(day_df['timestamp'], day_df['real_pow'], day_df['real_pow']+day_df['react_pow'], alpha=0.2, label=f"Reactive Power")
        axx = ax.twinx()
        axx.plot(day_df['timestamp'], day_df['pow_factor'], label=f"Power Factor")
        axx.set_ylabel("PF")
        axx.set_ylim([0., 1.])
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.gcf().autofmt_xdate()
        ax.set_xlim([date_on, date_next])
        ax.set_ylim([0, 12000])
        ax.legend()
        ax.set_ylabel("VA/W/VAR")

        #plt.show()
        IObytes = io.BytesIO()
        plt.savefig(IObytes, format='png')
        IObytes.seek(0)
        graph_pow = base64.b64encode(IObytes.read()).decode()
        print(graph_pow[:32])

    if 1:
        print(f"-----plot PV  {len(sel_df)} {len(day_df)}")
        fig2, ax = plt.subplots(1, 4, figsize=(5, 2), sharey=True)
        ax11 = ax[0]
        ax11.fill_between(day_df['timestamp'], 0., day_df['pv1_vol']*day_df['pv1_cur'], alpha=0.7)
        ax11.set_xlim([date_on, date_next])
        ax11.set_ylim([0, 6000])
        ax11.set_ylabel("W/V")
        ax11.set_title("PV1")

        ax21 = ax11.twinx()
        ax21.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
        ax21.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax21.fill_between(day_df['timestamp'], 0., day_df['pv1_vol'], alpha=0.4)
        ax21.set_yticks([])
        ax21.set_ylim([0, 500])

        ax12 = ax[1]
        ax12.fill_between(day_df['timestamp'], 0., day_df['pv2_vol']*day_df['pv2_cur'], alpha=0.7)
        #ax12.tick_params(axis='both', which='both', bottom='off', top='off', left='off', right='off')
        ax12.set_xlim([date_on, date_next])
        ax12.set_ylim([0, 6000])
        ax12.set_title("PV2")
        ax22 = ax12.twinx()
        ax22.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
        ax22.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax22.fill_between(day_df['timestamp'], 0., day_df['pv2_vol'], alpha=0.4)
        #ax22.tick_params(axis='both', which='both', bottom='off', top='off', left='off', right='off')
        ax22.set_yticks([])
        #plt.setp(ax22.get_yticklabels(), visible=False)
        ax22.set_ylim([0, 500])


        ax13 = ax[2]
        ax13.fill_between(day_df['timestamp'], 0., day_df['pv3_vol'] * day_df['pv3_cur'], alpha=0.7)
        ax13.set_xlim([date_on, date_next])
        ax13.set_ylim([0, 6000])
        ax13.set_title("PV3")
        ax23 = ax13.twinx()
        ax23.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
        ax23.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax23.fill_between(day_df['timestamp'], 0., day_df['pv3_vol'], alpha=0.4)
        #ax23.tick_params(axis='both', which='both', bottom='off', top='off', left='off', right='off')
        ax23.set_yticks([])
        #plt.setp(ax22.get_yticklabels(), visible=False)
        ax23.set_ylim([0, 500])

        ax14 = ax[3]
        ax14.fill_between(day_df['timestamp'], 0., day_df['pv4_vol'] * day_df['pv4_cur'], alpha=0.7)
        #ax14.set_yticks([])
        ax14.set_xlim([date_on, date_next])
        ax14.set_ylim([0, 6000])
        ax14.set_title("PV4")
        ax24 = ax14.twinx()
        ax24.xaxis.set_major_formatter(mdates.DateFormatter('%H'))
        ax24.xaxis.set_major_locator(mdates.HourLocator(interval=12))
        ax24.fill_between(day_df['timestamp'], 0., day_df['pv4_vol'], alpha=0.4)
        #ax24.set_yticks([])
        ax24.set_ylim([0, 500])

        #plt.show()
        IObytes = io.BytesIO()
        plt.savefig(IObytes, format='png')
        IObytes.seek(0)
        graph_pv = base64.b64encode(IObytes.read()).decode()
        print(graph_pv[:32])
    if 1:
        print(f"-----plot Temp  {len(sel_df)} {len(day_df)}")
        fig3, ax = plt.subplots(figsize=(5, 2))
        plt.title('Temperature', fontsize=12)
        plt.gca().xaxis.set_major_formatter(mdates.DateFormatter('%H:%M'))
        plt.gca().xaxis.set_major_locator(mdates.HourLocator(interval=4))
        plt.gcf().autofmt_xdate()
        ax.plot(day_df['timestamp'], day_df['pv1_temp'], label=f"PV Temp.1")
        ax.plot(day_df['timestamp'], day_df['pv2_temp'], label=f"PV Temp.2")
        ax.plot(day_df['timestamp'], day_df['inv_temp'], label=f"INV. Temp.")
        ax.set_xlim([date_on, date_next])
        ax.set_ylim([0, 150])
        ax.legend()
        ax.set_ylabel("℃")

        #plt.show()
        IObytes = io.BytesIO()
        plt.savefig(IObytes, format='png')
        IObytes.seek(0)
        graph_temp = base64.b64encode(IObytes.read()).decode()
        print(graph_temp[:32])

    return {"request": request, "device": device,
            "selections": selections, "selected": selected,
            "sel_df": sel_df, "day_df": day_df,
            "graph_pow": graph_pow, "graph_pv": graph_pv, "graph_temp": graph_temp}

@app.get("/view", response_class=HTMLResponse)
async def view_device(request: Request, device: str, selected: str = None):
    params = request.query_params
    print(f'Base: {request.base_url}, URL:{request.url._url}, Params:{params}')

    ctx = data_view_device (request, device, selected)

    return templates.TemplateResponse("view_device.html", ctx)

@app.post("/view")
def view_device_post(request: Request, selected: str = Form(...)):

    ctx = data_view_device(request, device, selected)

    return templates.TemplateResponse("view_device.html", ctx)

if __name__ == "__main__":
    uvicorn.run("ieee_2030_5.__Monitor_Server:app", host="0.0.0.0", port=8000, reload=True)
