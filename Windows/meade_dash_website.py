from dash import Dash, html, dcc, Input, Output, callback, State, ctx
import redis
import time
from datetime import datetime, timedelta
import os
import glob
from astropy.io import fits
from configparser import ConfigParser


config = ConfigParser()
config.read("config_temp.ini")
config_data = config["OFFICIAL"]

HOST_IP = config_data["host_ip"]
REDIS_PORT = config_data["redis_port"]
r = redis.Redis(host=HOST_IP, port=REDIS_PORT)

image_path = config_data["image_path"]

info_list1 = 'result'
info_list2 = 'cam_info'
keys1 = ['decide', 'datetime', 'mode', 'filter', 'exptime']
keys2 = ['datetime', 'exptime', 'filter', 'temp']


def latest_file_path(image_path):
    list_of_files = glob.glob(f'{image_path}/*.png')
    latest_file = max(list_of_files, key=os.path.getctime)
    latest_file = latest_file.split('\\')[-1]
    return f'assets/images/{latest_file}'

def date_time():
    date = str(datetime.now().date())
    time = str(datetime.now().strftime('%H:%M:%S.%f')[:-4])
    return f'{date}T{time}'

def get_data(name, keys):
    try:
        info_list = r.get(name)
        while info_list is None:
            info_list = r.get(name)
            # time.sleep(1)
        info_list = info_list.decode('utf-8')
        info_list = info_list.split('#')
        dictionary = dict.fromkeys(keys)
        for i, k in enumerate(dictionary):
            dictionary[k] = info_list[i]
        try:
            dictionary['datetime'] = datetime.strptime(dictionary['datetime'], '%Y-%m-%dT%H:%M:%S.%f')
        except:
            pass
        return dictionary
    except redis.ConnectionError:
        return {key: 'Error' for key in keys}


def send_data(exp_time, filter_pos, temp):
    datetime = date_time()
    data_str = '#'.join([str(datetime), str(exp_time), str(filter_pos), str(temp)])
    print(data_str)
    str_dict = {'website_value': data_str}
    r.mset(str_dict)
    result = r.get('website_value').decode("utf-8")
    return result

app = Dash(__name__)

app.title = 'Meade'

app.layout = html.Div([

    html.Div([
        html.Div(id='image')
    ], className='column1'),

    html.Div([
        html.Div([
            html.H1(id='exptime', children="Exptime: "),
            dcc.Input(id='input-exp', type='number', placeholder='change exptime', min=0, debounce=True)
        ]), 
        html.Div([
            html.H1(id='filter-info', children="Filter: ") , 
            dcc.Dropdown(config_data["filters_list"][2:-2].split("', '"), id='input-filter', placeholder='change filter')
        ]),
        html.Div([
            html.H1(id='temperature', children="Temp: "), 
            dcc.Input(id='input-temp', type='number', placeholder='change temp', min=-20, max=100)
        ]),
        html.Div([
            html.Button('Submit', id='submit-but', n_clicks=0), 
            html.Div(id='container-button-timestamp')
        ]), 
    ], className='column2'),

    html.Div([
        html.Div(id='latest-timestamp')
    ], className='column3'),

    dcc.Interval(
        id='interval-component', 
        interval=1000,
        n_intervals=0)

])


@app.callback(
    [Output(component_id='latest-timestamp', component_property='children')],
    [Input('interval-component', 'n_intervals')]
)
def update_timestamp(interval):
    return [html.Span(datetime.now().strftime('%Y-%m-%d %H:%M:%S'))]

@callback(
    Output('image', 'children'),
    Input('interval-component', 'n_intervals')
)
def img_update(n_intervals):
    image = latest_file_path(image_path)
    return html.Img(src=image)

@callback(
    Output('exptime', 'children'), 
    Input('input-exp', 'value')
)
def update_exptime(value):
    data2 = get_data(info_list2, keys2)
    exptime_info = data2['exptime'].split('.')[0]
    msg = 'Exptime: ' + str(exptime_info) +  ' [s]'
    return msg

@callback(
    Output('filter-info', 'children'), 
    Input('input-filter', 'value')
)
def update_filter(value):
    data2 = get_data(info_list2, keys2)
    msg = 'Filter: ' + str(data2['filter'])
    return msg

@callback(
    Output('temperature', 'children'), 
    Input('input-temp', 'value')
)
def update_temp(value):
    data2 = get_data(info_list2, keys2)
    msg = 'Temp: ' + str(data2['temp']) + ' ℃'
    return msg

@app.callback(
    Output('container-button-timestamp', 'children'), 
    [
        Input('submit-but', 'n_clicks'),
        Input('input-exp', 'n_submit'),
        Input('input-temp', 'n_submit'),
    ],
    [
        State('input-exp', 'value'),
        State('input-filter', 'value'),
        State('input-temp', 'value')
    ],
)
def button_click(n_clicks, n_submit_exp, n_submit_temp, exp_time, filter_pos, temp):
    triggered = ctx.triggered_id
    msg = 'Press to change values'
    if triggered == 'submit-but' or triggered in ['input-exp', 'input-temp']:
        msg = 'Changing values...'
        send_data(exp_time, filter_pos, temp) 
    return [
        html.Div(msg), 
        html.Script("window.location.reload();")
    ]

if __name__ == '__main__':
    app.run(debug=True)
