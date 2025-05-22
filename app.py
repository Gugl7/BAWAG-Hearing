import streamlit as st
import datetime 
import altair as alt
import pandas as pd
from statsmodels.tsa.arima.model import ARIMA

# Setting the number of visualizations session state variable to dictate number of visualizations shown
if "n_visualizations" not in st.session_state:
    st.session_state.n_visualizations = 1
if st.session_state.n_visualizations > 1:
    st.set_page_config(layout="wide")
else:
    st.set_page_config(layout="centered")

# Connecting to Snowflake database cached as a resource to avoid multiple connections
@st.cache_resource
def connect_to_db(name:str="zip"):
    return st.connection(name, type="snowflake").session()

# Function to run SQL queries and return results as pandas DataFrame cached
@st.cache_data
def run_query(_conn, query:str, params:list=None):
    return _conn.sql(query, params=params).to_pandas()

# Function to display the title and description of the app
st.title("Data Analysis for Global Weather and Climate data")
st.text("by Marko Gugleta")

conn = connect_to_db("zip")

def element_select_visualization(index:int=0):
    """
    Function to return the element for visualization selection.
    """
    return st.selectbox(
        label="Select visualization",
        options=("Bar Chart", "Line Chart", "Heat Map", "Forecast Prediction"),
        index=0,
        key="visualization"+str(index),
    ), index

def add_filters(index:int=0, type:str="Bar Chart"):
    """
    Add filters for visualization selection, gives back filters based on the type of visualization.
    """
    query = (
    """
    SELECT DISTINCT
        city
    FROM
        zip_codes.public.history_day
    ORDER BY city ASC
    """)
    cities = run_query(conn, query)
    if type == "Heat Map":
        city = st.multiselect(
            label="Select City names",
            options=cities,
            default=cities[0:5],
            key="city"+str(index),
        )
    else:
        city = st.selectbox(
            label="Select City name",
            options=cities,
            index=0,
            key="city"+str(index),
        )
    
    if type != "Forecast Prediction":
        left_column, right_column = st.columns(2)
        with left_column:
            start_date = st.date_input("Start Date", datetime.date(2023, 5, 21), key="start_date"+str(index), format="YYYY-MM-DD")
        with right_column:
            end_date = st.date_input("End Date", datetime.date.today(), key="end_date"+str(index), format="YYYY-MM-DD")
    else:
        start_date = None
        end_date = None

    if type == "Heat Map" or type == "Bar Chart" or type == "Forecast Prediction":
        features = st.selectbox(
            "Features selected for visualization",
            options=["Temperature", "Precipitation", "Humidity", "Windspeed"],
            key="features"+str(index),
        )
    else:
        features = st.multiselect(
            "Features selected for visualization",
            options=["Temperature", "Precipitation", "Humidity", "Windspeed"],
            default=["Temperature"],
            key="features"+str(index),
        )
    
    return city, start_date, end_date, features

def visualize_bar_chart(index:int=0):
    """
    Function to visualize the bar chart based on the selected filters.
    """
    city, start_date, end_date, features = add_filters(index=index, type="Bar Chart")
    
    history = "AVG_TEMPERATURE_AIR_2M_F"
    climatology = "AVG_OF__DAILY_AVG_TEMPERATURE_AIR_F"
    if features == "Temperature":
        history = "AVG_TEMPERATURE_AIR_2M_F"
        climatology = "AVG_OF__DAILY_AVG_TEMPERATURE_AIR_F"
    elif features == "Precipitation":
        history = "TOT_PRECIPITATION_IN"
        climatology = "AVG_OF__POS_DAILY_TOT_PRECIPITATION_IN"
    elif features == "Humidity":
        history = "AVG_HUMIDITY_RELATIVE_2M_PCT"
        climatology = "AVG_OF__DAILY_AVG_HUMIDITY_RELATIVE_PCT"
    elif features == "Wind Speed":
        history = "AVG_WIND_SPEED_10M_MPH"
        climatology = "AVG_OF__DAILY_AVG_WIND_SPEED_10M_MPH"
    
    query = f"""
    SELECT
        EXTRACT(YEAR FROM h.DATE_VALID_STD) || '-' || LPAD(EXTRACT(MONTH FROM h.DATE_VALID_STD)::VARCHAR, 2, '0') AS year_month,
        EXTRACT(YEAR FROM h.DATE_VALID_STD) AS year,
        EXTRACT(MONTH FROM h.DATE_VALID_STD) AS month,
        AVG(h.{history}) AS historical,
        AVG(c.{climatology}) AS climatology,
    FROM
        zip_codes.public.history_day h
    JOIN 
        zip_codes.public.climatology_day c ON h.CITY = c.CITY AND h.DOY_STD = c.DOY_STD
    WHERE 
        h.CITY = ?
        AND h.DATE_VALID_STD BETWEEN ? AND ?
    GROUP BY
        year, month
    ORDER BY
        year, month;
    """
    st.divider()
    if city or start_date or end_date:
        df = run_query(conn, query, params=[city, start_date, end_date])
        df.drop(['YEAR', 'MONTH'], axis=1, inplace=True)
        df.set_index("YEAR_MONTH", inplace=True)
        df = df.astype('float')
        st.header("Monthly average")
        st.bar_chart(df, stack=False, x_label="Time", y_label=features, use_container_width=True)

def visualize_line_chart(index:int=0):
    """
    Function to visualize the line chart based on the selected filters.
    """
    city, start_date, end_date, features = add_filters(index=index, type="Line Chart")
    sql_query = f"""
    SELECT
        DATE_VALID_STD,
        AVG_TEMPERATURE_AIR_2M_F as TEMPERATURE,
        TOT_PRECIPITATION_IN as PRECIPITATION,
        AVG_HUMIDITY_RELATIVE_2M_PCT as HUMIDITY,
        AVG_WIND_SPEED_10M_MPH as WINDSPEED
    FROM 
        zip_codes.public.history_day
    WHERE
        CITY = ?
        AND DATE_VALID_STD BETWEEN ? AND ?
    ORDER BY 
        DATE_VALID_STD
    """
    st.divider()
    if city or start_date or end_date:
        df = run_query(conn, sql_query, params=[city, start_date, end_date])
        st.header("Trend over time")
        if features:
            st.line_chart(df, x="DATE_VALID_STD", y=[f.upper() for f in features], x_label="Time", y_label="Values", use_container_width=True)

def visualize_heat_map(index:int=0):
    """
    Function to visualize the heat map based on the selected filters.
    """
    city, start_date, end_date, features = add_filters(index=index, type="Heat Map")
    st.divider()
    sql_query = f"""
    SELECT
        h.DATE_VALID_STD AS observation_date,
        h.CITY AS city_name,
        (h.AVG_TEMPERATURE_AIR_2M_F - c.AVG_OF__DAILY_AVG_TEMPERATURE_AIR_F) AS temperature,
        (h.TOT_PRECIPITATION_IN - c.AVG_OF__POS_DAILY_TOT_PRECIPITATION_IN) AS precipitation,
        (h.AVG_HUMIDITY_RELATIVE_2M_PCT - c.AVG_OF__DAILY_AVG_HUMIDITY_RELATIVE_PCT) AS humidity,
        (h.AVG_WIND_SPEED_10M_MPH - c.AVG_OF__DAILY_AVG_WIND_SPEED_10M_MPH) AS windspeed,
    FROM
        zip_codes.public.history_day h
    JOIN
        zip_codes.public.climatology_day c
        ON h.POSTAL_CODE = c.POSTAL_CODE AND h.DOY_STD = c.DOY_STD
    WHERE
        h.CITY IN ({', '.join(["'" + city +  "'" for city in city])})
        AND h.DATE_VALID_STD BETWEEN ? AND ?
    ORDER BY
        h.CITY, h.DATE_VALID_STD;
    """
    st.header("Difference in values")
    if city or start_date or end_date:
        if len(city) <= 0:
            return
        df = run_query(conn, sql_query, params=[start_date, end_date])

        df['OBSERVATION_DATE'] = pd.to_datetime(df['OBSERVATION_DATE'])
        source = pd.DataFrame({
            'x': df['OBSERVATION_DATE'],
            'y': df['CITY_NAME'],
            'z': df[features.upper()]
        })

        ch = alt.Chart(source).mark_rect().encode(
            alt.X('x:O').axis(title='Time', format="%Y-%m", formatType="time", labelAngle=-45),
            alt.Y('y:O', title='Cities'),
            alt.Color('z:Q')
        )        
        st.altair_chart(ch, use_container_width=True)

def visualize_forecast_prediction(index:int=0):
    """
    Function to visualize prediction of the selected features based on the selected filters.
    """
    city, _, _, feature = add_filters(index=index, type="Forecast Prediction")
    train_button = st.button("Train Model", key="train_model"+str(index), help="Train the model for forecast prediction")
    
    st.header("Forecast Prediction for the next 14 days")
    
    if train_button:
        sql_query = f"""
        SELECT
            DATE_VALID_STD,
            AVG_TEMPERATURE_AIR_2M_F as TEMPERATURE,
            TOT_PRECIPITATION_IN as PRECIPITATION,
            AVG_HUMIDITY_RELATIVE_2M_PCT as HUMIDITY,
            AVG_WIND_SPEED_10M_MPH as WINDSPEED
        FROM 
            zip_codes.public.history_day
        WHERE
            CITY = ?
        ORDER BY 
            DATE_VALID_STD
        """
        df = run_query(conn, sql_query, params=[city])
        prediction_df = df[["DATE_VALID_STD", feature.upper()]]
        
        series = prediction_df[feature.upper()].astype(float)
        train, test = series[:-14], series[-14:]
        output=[]
        
        for t in test:
            model = ARIMA(train, order=(1,1,1))
            model_fit = model.fit()
            temp_output = model_fit.forecast(steps=1)
            train = pd.concat([train, temp_output])
            output.append(temp_output)
        
        forecast_dates = prediction_df["DATE_VALID_STD"].iloc[-14:].reset_index(drop=True)
        forecast_values = pd.DataFrame([val.iloc[0] for val in output], index=forecast_dates, columns=["Forecast"])
        actual_values = test.reset_index(drop=True)
        forecast_values[feature.upper()] = actual_values.values
        forecast_values.reset_index(inplace=True)
        st.line_chart(forecast_values, x="DATE_VALID_STD", y=["Forecast", feature.upper()], use_container_width=True)

def visualize(args:tuple=None):
    """
    Function to select the visualization based on the arguments.
    """
    if args is None:
        print("ERROR: Wrong option selected.")
        st.error('ERROR: Wrong option selected.', icon="🚨")
    type, index = args
    if type == "Bar Chart":
        visualize_bar_chart(index=index)
    elif type == "Line Chart":
        visualize_line_chart(index=index)
    elif type == "Heat Map":
        visualize_heat_map(index=index)
    elif type == "Forecast Prediction":
        visualize_forecast_prediction(index=index)
    else:
        print("ERROR: Wrong option selected.")
        st.error('ERROR: Wrong option selected.', icon="🚨")

# Buttons to add or remove visualizations
button_add = st.button("Add Visualization", key="add_visualization", help="Add a new visualization")
button_remove = st.button("Remove Visualization", key="remove_visualization", help="Remove a visualization")
if button_add:
    if st.session_state.n_visualizations < 3:
        st.session_state.n_visualizations += 1    
        st.rerun()
if button_remove:
    if st.session_state.n_visualizations > 1:
        st.session_state.n_visualizations -= 1
        st.rerun()

# Sections for visualizations
columns = st.columns(st.session_state.n_visualizations)
for i in range(st.session_state.n_visualizations):
    with columns[i]:
        visualize(element_select_visualization(index=i))


# Additional information
st.divider()
with st.expander("See additional information about the Data and the project", expanded=False):
    st.write('''
        You can have one or more visualizations at the same time, up to three. It is possible to select the type of visualization, the city name, the date range and the features to be visualized. The data is taken from a Snowflake database and is updated daily. The data is stored in two tables: history_day and climatology_day. The history_day table contains the actual weather data, while the climatology_day table contains the average weather data for each day of the year.
        The data is stored in Fahrenheit, inches, miles per hour and percentages. The data spans from 2023-05-21 to today. There are around 543,000 rows in the history_day table and around 272,000 rows in the climatology_day table.
    ''')
