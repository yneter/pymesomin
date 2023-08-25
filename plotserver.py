import dash
from dash import dcc, html, ctx, clientside_callback

import plotly.graph_objects as go
import numpy as np
import re
import datetime
import sys
import json

from dash.dependencies import Input, Output, State
from flask import request

from pymesomin.magnetsafety import MagnetSafeCryofast


magnet_safe = None

    
class PlotServer :
    def reset_measurement(self, reset_data=True) :
        self.paused = False
        self.stop = False
        self.start_time  = datetime.datetime.now()
        self.last_update_time = None
        self.eta_time = ""
        self.updates = False
        self.instruments = []
        self.progress = "0"
        self.figure_title = ""
        self.log_values = "" 
        if reset_data:
            self.time_offset = 0
            self.last_time_without_offset = 0
            self.parray = None

    def __init__(self):
        self.reset_measurement()
        self.documents = { } # don't reset documentation 
        self.prompt = ""
        self.prompt_reply = ""


        
pls = PlotServer()
        

app = dash.Dash(__name__, update_title=None) 
app.title = 'Cryofast'


def make_figure():    
    fig = go.FigureWidget()
    fig.update_layout( legend=dict(orientation="h", yanchor="bottom", y=1.02,
                                  xanchor="left", x=0, font = dict(size = 24)),
                      yaxis = dict(tickfont = dict(size=20)),
                      xaxis = dict(tickfont = dict(size=20)),
                      paper_bgcolor='rgb(228,254,254)',
                      plot_bgcolor='rgb(220,220,220)',
                      margin=dict(l=15, r=15, t=15, b=15),
    )
    return fig


figure = make_figure()

def make_layout() :
    return html.Div( [
        # create a store to keep figure data locally 
        dcc.Store(
            id="figure_local_store",
            data=[
            ],
        ),
        html.Div([
        dcc.Dropdown(
            id = 'show_menu',
            options=[
                {'label': 'Measurement', 'value': 'measurement'},
                {'label': 'Instruments',  'value': 'instrument'},
                {'label': 'Prompt',  'value': 'prompt'},
                {'label': 'Quick plots',  'value': 'plots'} ],
            value = 'measurement'
        )]),
        html.Div(id='measurement_menu', style= {'display': 'block'}, children=[
            
        html.H1( [ html.Div(id='magnetstyle', children=html.Div(id='magnetstate') ),
                  ] ), 
        html.Div([
            html.Button('Pause', id='pause-button', n_clicks=0 ),
            html.Div( style={'padding': 5, 'flex': 1}  ),
            html.Div(id='last_update_style', children=html.Div( id='last_update', children = 'Last: '  )),
            html.Progress(id='progress', value=0),
            html.Div( id='progress_eta', children = 'ETA: '  ),
            html.Div( style={'padding': 5, 'flex': 1}  ),  
            html.Button('STOP', id='stop-button', n_clicks=0),
        ], style={'display': 'flex', 'flex-direction': 'row', 'width': '100%'}),
        html.Div(id='measurement_title'),
        html.Div(id='device_list'),
        dcc.Graph(id='graph', figure=figure, style={'height': '70vh'}, ), 
        html.Div([
            html.Div(children='X:', style={'padding': 5 }),
            html.Div( [ dcc.Dropdown( id='xaxisopt' ) ] , style={ 'width':'15%' } ),     
            html.Div(style={'width': '5%' }),
            html.Div(children='Y:', style={'padding': 5 }),
            html.Div( [ dcc.Dropdown( id='yaxisopt' , options=['from legend', 'show all', 'hide all'], value='from legend') ] , style={ 'width':'15%' } ),     
            html.Div(style={'width': '5%' }),
            html.Div(children='X scale:', style={'padding': 5, } ),   
            html.Div([ dcc.Dropdown( id='xaxis-type', options=['linear', 'log', 'inverse'], value='linear' ) ]
                     , style={'width' : '10%' } ),     
            html.Div(style={'width': '10%' }),
            html.Div(children='Y scale:', style={'padding': 5, } ), 
            html.Div([ dcc.Dropdown( id='yaxis-type', options=['linear', 'log', 'inverse'], value='linear' ) ]
                     , style={'width' : '10%' } ),     
        ], style={'display': 'flex', 'flex-direction': 'row'}),
        dcc.Markdown(id="log_instrument_output"),
        dcc.Interval(id="interval", interval=300, n_intervals = 0),
        dcc.Interval(id="interval_slow", interval=1000, n_intervals = 0),
        dcc.Interval(id="interval_magnet", interval=3000, n_intervals = 0),        
        ]),      
        html.Div(id='instrument_menu', style= {'display': None}, children=[
            html.Div( [
                html.Div("Instruments:"),
                html.Div( [ dcc.RadioItems(id='instruments', labelStyle={'display':'block'} ) ] ), ]
             ),
            html.Br(),
            html.Div (children="Instructions:" ),
            dcc.Markdown(id="instruction_text")
        ] ), 
        html.Div(id='graph_menu', style= {'display': None}, children=[
            html.Div("Graphs:"),
            dcc.Graph(id='otherplots', figure=other_plots, style={'height': '70vh'}, ), 
        ] ),         
        html.Div(id='prompt_menu', style= {'display': None}, children=[
            dcc.Textarea(id='prompt-state',
                value=
"""sequence of set and get instructions to be executed during sweep and record
examples (pymeasure style):     
set sr1.frequency 137 
get sr1.sensitivity
""",
               style={'width': '100%', 'height': 200}, ),
            html.Button('Submit', id='prompt-state-button', n_clicks=0),
            html.Br(),
            html.Div(id='prompt-input', style={'whiteSpace': 'pre-line'}),
            html.Br(),
            html.Div (children="Response:", style={'color' : 'blue'} ), 
            html.Div(id='prompt-response', style={'whiteSpace': 'pre-line'})
       ])
    ])


other_plots = make_figure()
other_plots.add_trace(go.Scatter(name = "cos", visible=True )) 
    
    
app.layout = make_layout()


@app.callback(
   Output(component_id='measurement_menu', component_property='style'),
   Input(component_id='show_menu', component_property='value'))
def show_hide_element(menu_state):
    if menu_state == 'measurement':
        return {'display': 'block'}
    else:
        return {'display': 'none'}



@app.callback(
   Output(component_id='prompt_menu', component_property='style'),
   Input(component_id='show_menu', component_property='value'))
def show_hide_prompt(menu_state):
    if menu_state == 'prompt':
        return {'display': 'block'}
    else:
        return {'display': 'none'}

    


@app.callback(
   Output(component_id='graph_menu', component_property='style'),
   Input(component_id='show_menu', component_property='value'))
def show_hide_element_graph(menu_state):
    if menu_state == 'plots':
        return {'display': 'block'}
    else:
        return {'display': 'none'}



@app.callback(
   Output(component_id='instrument_menu', component_property='style'),
   Output(component_id='instruments', component_property='options'),
   Input(component_id='show_menu', component_property='value'))
def show_hide_element_menu(menu_state):
    if menu_state == 'instrument':
        return {'display': 'inline-block'}, list(pls.documents.keys())
    else:
        return {'display': 'none'},  list(pls.documents.keys())


@app.callback(
    Output(component_id='instruction_text', component_property='children'),
    Input(component_id='instruments', component_property='value')
    ) 
def show_documentation(instru):
    global pls 
    if pls.documents and instru in pls.documents.keys():
        return pls.documents[instru]
   
@app.callback(
    Output(component_id='log_instrument_output', component_property='children'),
    Input('interval_slow', 'n_intervals'),
    ) 
def show_log_instrument_output(n):
    global pls 
    return "log instument values : \n\r {}".format(pls.log_values)   
    
@app.callback(Output('pause-button', 'style'),
              Input('pause-button', 'n_clicks'),
)
def pause_pressed(n_clicks):
    global pls
    if n_clicks % 2 == False:
        pls.paused = False
        return { 'color': 'black', 'width': '15%' }
    else :
        pls.paused = True
        return { 'color': 'orange', 'width': '15%' }


@app.callback(Output('stop-button', 'style'),
              Input('stop-button', 'n_clicks'),
)
def stop_pressed(n_clicks):
    global pls
    if n_clicks > 0:
        pls.stop = True
    if n_clicks % 2 == False:
        return { 'color': 'blue',  'background-color': 'red', 'width': '15%' }
    else :
        return { 'color': 'black',  'background-color': 'red', 'width': '15%' }

    

@app.callback( Output('last_update', 'children'),
               Output('progress', 'value'),
               Output('progress_eta', 'children'),    
               Input('interval_slow', 'n_intervals'),
)
def update_progress(n) :
    """ For unknown reasons, problems with progress callback in debug mode """ 
    if pls.last_update_time is not None:
        last_time = "Last : " + pls.last_update_time.strftime("%H:%M:%S")
    else:
        last_time = ""
    return last_time, str(pls.progress) , pls.eta_time 


@app.callback( Output('magnetstate', 'children'),
               Input('interval_magnet', 'n_intervals'),
)
def update_magnet_state(n) :
    if magnet_safe is not None:
        magnet_safe.update()
        return magnet_safe.message() #,
    else:
        return "Magnet safety disabled"


@app.callback( Output('magnetstyle', 'style'),
               Input('interval_magnet', 'n_intervals'),
)
def update_magnet_style(n) :
   if magnet_safe is None or magnet_safe.mag_error: 
       color = 'orange'
   else : 
       color = 'darkgreen'
   return { 'color': color }



@app.callback( Output('last_update_style', 'style'),
               Input('interval_magnet', 'n_intervals'),
)
def update_magnet_style(n) :
    if pls.last_update_time is not None:
        diff_minutes = (datetime.datetime.now() - pls.last_update_time).total_seconds() / 60.
        if diff_minutes < 1: 
            return { 'color': 'darkgreen' }    
    return { 'color': 'black' }
            

@app.callback(Output('device_list', 'children'),
              Output('measurement_title', 'children'),
              Input('interval_slow', 'n_intervals'),
)
def update_instruments(n) :
    global pls
    return 'Measured: {}'.format(' '.join(pls.instruments)), \
        'Run: {}'.format(pls.figure_title), \


@app.callback(Output('xaxisopt', 'options'),
              Output('xaxisopt', 'value'),
              Input('interval_slow', 'n_intervals'),
              Input('xaxisopt', 'value'),
)
def update_axis_opt(n, xaxisval) :
    global pls
    xaxis_choices = pls.instruments
    if xaxisval is None and len(xaxis_choices) > 0:
        xaxisval = xaxis_choices[0]        
    return xaxis_choices, xaxisval



@app.callback(Output('figure_local_store', 'data'),
              Input('interval', 'n_intervals'),
)
def update_local_data_store(n):
    global pls
    if pls.updates and pls.parray is not None:
        for j in range( min( len(figure.data), pls.parray.shape[1] ) ):
            figure.data[j].y = pls.parray[:,j].tolist()
        figure.update_layout(uirevision='constant')    
    pls.updates = False
    return figure



"""
@app.callback(
    Output('clientside-figure-json', 'children'),
    Input('figure_local_store', 'data')
)
def generated_figure_json(data):
    return '```\n'+json.dumps(data, indent=2)+'\n```'
"""

clientside_callback(
    """
    function(fig, xaxis_type, yaxis_type, xaxis_val, yaxis_val) {
        let xdata = fig['data'][0]['y'];
        for (d of fig['data']) {
            if (d['name'] == xaxis_val) {
               xdata = d['y']
            }
        }
        for (d of fig['data']) { 
           d['x'] = xdata;
        }
        if (yaxis_val == 'show all') { 
           for (n in fig['data']) { 
              if (n > 0) { 
                 fig['data'][n]['visible'] = true;
              }
           }
        }
        if (yaxis_val == 'hide all') { 
           for (d of fig['data']) { 
              d['visible'] = 'legendonly';
           }
        }
        if (xaxis_type == 'log' || xaxis_type == 'linear') { 
           fig['layout']['xaxis']['type'] = xaxis_type
        } 
        if (yaxis_type == 'log' || yaxis_type == 'linear') { 
           fig['layout']['yaxis']['type'] = yaxis_type
        } 
        if (xaxis_type == 'inverse') { 
           for (d of fig['data']) { 
              d['x'] = d['x'].map( value => 1./value );
           }
        }
        if (yaxis_type == 'inverse') { 
           for (d of fig['data']) { 
              d['y'] = d['y'].map( value => 1./value );
           }
        }
        if (xaxis_type == 'log') { 
           for (d of fig['data']) { 
              d['x'] = d['x'].map( value => Math.abs(value) );
           }
        }
        if (yaxis_type == 'log') { 
           for (d of fig['data']) { 
              d['y'] = d['y'].map( value => Math.abs(value) );
           }
        }
        return fig;
    }
    """,
    Output('graph', 'figure'),
    Input('figure_local_store', 'data'),
    Input('xaxis-type', 'value'),
    Input('yaxis-type', 'value'),
    Input('xaxisopt', 'value'),
    Input('yaxisopt', 'value')
)


@app.callback(Output('otherplots', 'figure'),
              Input('interval', 'n_intervals')             
)
def update_other_plots(n):
    global pls
    try: 
        other_plots.data[0].y = pls.other_ploty
        other_plots.data[0].x = pls.other_plotx
    except AttributeError:
        pass
    other_plots.update_layout(uirevision='constant')
    return other_plots

@app.callback(
    Output('prompt-input', 'children'),
    Input('prompt-state-button', 'n_clicks'),
    State('prompt-state', 'value')
)
def update_prompt_input(n_clicks, value):
    global pls
    if n_clicks > 0:
        pls.prompt = value
        return 'You have entered: \n{}'.format(value)



@app.callback(
    Output('prompt-response', 'children'),
    Input('interval_slow', 'n_intervals'),
)
def update_prompt_reply(n):
    global pls
    return pls.prompt_reply
    
server = app.server
 
@server.route('/instruments')
def instruments():
    global pls
    pls.documents = request.args
    return { 'message' : 'received' }


@server.route('/logvalues')
def log_instruments():
    global pls
    pls.log_values = request.args["log_values"].replace('#', '-').replace('\n', '\n\r')
    return { 'message' : 'received' }

"""
updates the numpy array containing measurement pls.parray by appending a row with new data 
if the number of rows > max_rows, keeps only even rows to reduce size by half
"""
@server.route('/update')
def update():
    global pls
    max_rows = 4000
    pls.updates = True                
    vstr = request.args.get('values', "")
    if vstr: 
        varlist = list( map(float, re.split("\s+", vstr) ) )
        if pls.parray is None :
            pls.parray = np.asarray( [ varlist ] )
        else : 
            """
            In general time only flows forward, for mutiple record sequences we offset the 
            the time of the current record by the final time of the last record
            """
            if pls.instruments[0] == "time":
                if varlist[0] < pls.last_time_without_offset:
                    pls.time_offset += pls.last_time_without_offset
                pls.last_time_without_offset = varlist[0]
                varlist[0] += pls.time_offset

                
            try:
                if pls.parray.shape[0] > max_rows: 
                    print("reducing array size")
                    pls.parray = pls.parray[::2]
                pls.parray = np.append( pls.parray,  np.asarray( [ varlist ] ), axis=0 )
            except ValueError:
                pass
            
    pstr = request.args.get('progress', "")
    if pstr:
        pls.progress = pstr
        if float(pstr) > 0:
            pls.last_update_time = datetime.datetime.now()
            diff = pls.last_update_time - pls.start_time 
            pls.eta_time = "ETA: " + (pls.start_time + diff / float(pstr)).strftime("%H:%M:%S")
    return {
        'query_param': vstr
    }


@server.route('/start')
def start():
    global pls
    pls.updates = True
    vstr = request.args.get('measuring', "")
    if vstr:
        old_instruments = pls.instruments
        pls.reset_measurement()
        pls.instruments = re.split("\s+", vstr)
        if pls.instruments == old_instruments:
            """
            keep previous figure settings if measured instruments are unchanged 
            """
            pass
        else:
            figure.data = [ ]        
            trace_count = 0
            for dev in pls.instruments:
                if not dev:
                    continue
                if trace_count == 1:
                    figure.add_trace(go.Scatter(name = dev, visible=True ))
                else:
                    figure.add_trace(go.Scatter(name = dev, visible='legendonly' ))
                trace_count += 1
                
    pls.figure_title = request.args.get('title', "")
    return {
        'query_param': vstr
    }



@server.route('/paused')
def pause_active():
    return { 'paused' : pls.paused }


@server.route('/prompt')
def prompt_active():
    global pls
    message = pls.prompt
    pls.prompt = "" 
    return { 'prompt' : message }

@server.route('/promptreply')
def prompt_reply():
    global pls    
    vstr = request.args.get('reply', "")
    pls.prompt_reply = vstr
    return { 'promptreply' : True }


@server.route('/stop')
def stop_active():
    global pls 
    stop = pls.stop
    pls.stop = False
    return { 'stop' : stop }



@server.route('/serverside/experiment')
def server_experiment():
    global magnet_safe
    try:
        return { 'instruments' : magnet_safe.experiment.instruments_as_dictionary(),
                  'documents' : magnet_safe.experiment.documents_as_dictionary()
                }
    except AttributeError:
        return { 'instruments' : None }


@server.route('/serverside/run')
def server_experiment_get():
    """
    run set/get requests on server side experiment:
    example: http://127.0.0.1:8050/serverside/run?run=get bf.compressor,sr1.freq
    """
    global magnet_safe
    try: 
        reply = magnet_safe.experiment.run( request.args.get("run", ""), set_and_get_only = True )
        return { 'reply' : reply }
    except AttributeError:
        return { 'reply' : 'NoServerSideExperiment' }




@server.route('/otherplots')
def recieve_data_for_other_plots():
    global pls
    xstr = request.args.get('x', "")
    ystr = request.args.get('y', "")
    if xstr:
        pls.other_plotx = list( map(float, re.split("\s+", xstr) ) )
    if ystr:
        pls.other_ploty = list( map(float, re.split("\s+", ystr) ) )
    return { 'otherplots' : True }



def run_server(magnet_safety = True, port = 8050):
    global magnet_safe
    try:
        if not isinstance(magnet_safety, bool):
            magnet_safe = magnet_safety
        elif magnet_safety:
            magnet_safe = MagnetSafeCryofast()
        else:
            magnet_safe = None
    except (TimeoutError, OSError) as err :
        sys.stderr.write( str(err) + "\n" )
        sys.stderr.write( "Failed to connect to magnet/refrigerator\n" )
        sys.stderr.write( "Disable safety checks\n" )
        magnet_safe = None
    app.run(port=port)

if __name__ == '__main__':
    run_server()
