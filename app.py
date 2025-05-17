import streamlit as st

conn = st.connection("snowflake")
df = conn.query("SELECT * FROM newtable LIMIT 100;")

for row in df.itertuples():
    st.write(f"{row.MIN_TEMPERATURE_AIR_2M_F} has a :{row.MIN_TEMPERATURE_WETBULB_2M_F}:")