import streamlit as st
import openrouteservice as ors
import folium
import pandas as pd
import re
import math
import time  

st.set_page_config(layout="wide")

@st.cache_data(ttl=3600)  
def load_google_sheet_data(sheet_url):
    return pd.read_csv(sheet_url)

sheet_url = "https://docs.google.com/spreadsheets/d/1q8-nD8HJUps-mD1AVHDpB5klP-2yiivMSU1CXP5TKrU/export?format=csv&gid=1490221776"
sheet_url_2 = "https://docs.google.com/spreadsheets/d/1q8-nD8HJUps-mD1AVHDpB5klP-2yiivMSU1CXP5TKrU/export?format=csv&gid=1697726171"

log = load_google_sheet_data(sheet_url)
log['EAN'] = log['EAN'].astype(str).str.replace('.0',"")
mag = load_google_sheet_data(sheet_url_2)

order_type_mapping = {
    "STANDARD": [
        {"range": "STANDARD 0-15KM", "min_km": 0, "max_km": 15},
        {"range": "STANDARD 15-30KM", "min_km": 15, "max_km": 30},
        {"range": "STANDARD 30-50KM", "min_km": 30, "max_km": 50},
        {"range": "STANDARD >50KM", "min_km": 50, "max_km": None},
    ]
}

mag = mag[['Store_Name', 'Adresa_custom','Cod_Postal','Oras']]
mag['Adresa'] = mag['Adresa_custom'] + ',' + mag['Oras'] + ',' + mag['Cod_Postal'].astype(str)
mag['Adresa2'] = "Leroy Merlin" + " " + mag['Oras'] + ',' + mag['Cod_Postal'].astype(str)
mag = mag[['Store_Name', 'Adresa', 'Adresa2', 'Oras']]
mag['Adresa'] = mag['Adresa'].str.replace("Nr\.\s*", "", regex=True)
mag['Adresa'] = mag['Adresa'].str.replace("Sos\.\s*", "Soseaua ", regex=True)
mag['Adresa'] = mag['Adresa'].str.replace("Str\.\s*", "Strada ", regex=True)

st.title("Calculator tip de livrare")
st.markdown("<hr>", unsafe_allow_html=True)

client = ors.Client(key='5b3ce3597851110001cf6248571486db3ef0458ea19d9d4783b68797', requests_kwargs={'verify': False})


@st.cache_data(ttl=3600)
def geocode_address(address):
    geocode_result = client.pelias_search(address)
    coords = geocode_result['features'][0]['geometry']['coordinates']
    return coords


if 'product_entries' not in st.session_state:
    st.session_state['product_entries'] = [{'ean': '', 'quantity': 1}]  # Start with one product added by default


with st.sidebar:

    with st.container(border=True):
        store_names = mag['Store_Name'].unique()
        selected_store = st.selectbox("Selectați un magazin:", store_names, key="store_selection")
        
    store_info = mag[mag['Store_Name'] == selected_store].iloc[0]

    with st.container(border=True):
        start_address = store_info['Adresa']  
        st.subheader("Adresa de pornire")
        
        start_address_input = st.text_input("", start_address, key="start_address", max_chars=200)
        
    with st.container(border=True):
        st.subheader("Adresa de destinație")
    
        end_col1, end_col2, end_col3, end_col4, end_col5 = st.columns([2, 2, 2, 2, 2])

        with end_col1:
            end_street = st.text_input("Strada", "", key="end_street", max_chars=100)
    
        with end_col2:
            end_street_number = st.text_input("Nr.", "", key="end_street_number", max_chars=10)
    
        with end_col3:
            end_city = st.text_input("Oraș", "", key="end_city", max_chars=50)
    
        with end_col4:
            end_country = st.text_input("Țară", "", key="end_country", max_chars=50)

        with end_col5:
            end_postal_code = st.text_input("Cod poștal", "", key="end_postal_code", max_chars=10)


    # Add and remove products in the sidebar
    st.subheader("Produse")
    # Add product button
    if st.button("Adaugă produs"):
        st.session_state['product_entries'].append({'ean': '', 'quantity': 1})  # Adds a new product entry

    # Delete All Products button
    if st.button("Șterge toate produsele"):
        st.session_state['product_entries'] = []  # Clears all product entries

    # Display inputs for products and calculate weight for each product entry
    for i, entry in enumerate(st.session_state['product_entries']):
        st.write(f"**Produs {i + 1}:**")
        col1_inner, col2_inner = st.columns([3, 1])
        with col1_inner:
            # Manually enter EAN for each product (no selectbox)
            ean = st.text_input(f"Introduceți EAN-ul produsului {i+1}:", entry['ean'], key=f"ean_{i}")
            # Use st.session_state to hold the quantity and ensure it updates properly
            quantity_key = f"quantity_{i}"
            quantity = st.number_input(f"Introduceți cantitatea {i+1}:", min_value=1, step=1, 
                                       key=quantity_key, value=entry['quantity'], on_change=lambda: update_quantity(i))
            st.markdown("<hr>", unsafe_allow_html=True)


        with col2_inner:
            # Button to remove this product entry (placed on the right side)
            remove_button = st.button(f"Șterge produs {i+1}", key=f"delete_{i}")
            if remove_button:
                st.session_state['product_entries'].remove(entry)

        # Ensure EAN is provided before calculating weight
        if ean:
            product_data = log[log["EAN"] == ean]
            if not product_data.empty:
                product_name = product_data["DENUMIRE_PRODUS"].values[0]  # Get the product name
                weight_per_unit = product_data["GREUTATE_NET_KG"].values[0]
                
                # Display the product name
                st.write(f"**Produs selectat:** {product_name}")
                
                # Calculate the total weight for this product
                entry['ean'] = ean
                entry['quantity'] = quantity
                weight_total = weight_per_unit * quantity

                # Display total weight for each product entry
                st.write(f"**Greutate produs {i+1}:** {weight_total:.2f} kg")

# Function to handle quantity update in session state
def update_quantity(index):
    st.session_state['product_entries'][index]['quantity'] = st.session_state[f"quantity_{index}"]

# The main section where calculations and results are displayed
with st.container():
    # Initialize values for total weight and distance
    total_weight = 0
    total_distance_km = 0  # Initialize distance


    # Calculate overall total weight and distance automatically when both addresses are provided
    if start_address_input and end_street and end_street_number and end_city and end_country:
        # Include postal code if available in the destination address
        full_end_address = f"{end_street} {end_street_number}, {end_city}, {end_country}"
        if end_postal_code:
            full_end_address += f", {end_postal_code}"

        # Calculate total weight for all products
        for entry in st.session_state['product_entries']:
            ean = entry.get('ean', '')
            quantity = entry.get('quantity', 0)
            
            # Get product data from the log
            if ean:
                product_data = log[log["EAN"] == ean].iloc[0]
                weight_per_unit = product_data["GREUTATE_NET_KG"]
                
                # Calculate total weight for the current product
                total_weight += weight_per_unit * quantity

        try:
            # Geocode start and end addresses
            start_coords = geocode_address(start_address_input)
            end_coords = geocode_address(full_end_address)

            # Get route information from OpenRouteService
            route = client.directions(coordinates=[start_coords, end_coords], profile='driving-car', format='geojson')
            total_distance_meters = route['features'][0]['properties']['segments'][0]['distance']
            total_distance_km = total_distance_meters / 1000  # Convert to kilometers

            # Display total distance and weight
            st.write(f"**Distanța totală:** {total_distance_km:.2f} km")
            st.write(f"**Greutate totală:** {total_weight:.2f} kg")

            # Determine the order type based on the total distance
            order_type = None
            for order in order_type_mapping["STANDARD"]:
                if order["min_km"] <= total_distance_km < (order["max_km"] if order["max_km"] is not None else float('inf')):
                    order_type = order["range"]
                    break

            if order_type:
                st.write(f"**Tip de livrare recomandat:** {order_type}")
            else:
                st.write("**Tip de livrare nu a fost găsit pentru această distanță.**")

        except Exception as e:
            st.error(f"Error calculating the route: {e}")
    else:
        st.write("**Adresă de pornire și destinație completă necesare pentru calcularea distanței.**")

    st.markdown("<hr>", unsafe_allow_html=True)

    
    # Show checkboxes for hiding/showing the map
    show_map = st.checkbox("Arată harta", value=False)  # Checkbox for showing/hiding the map

    # Show the map only if the checkbox is checked and after the total calculation is complete
    if show_map and start_address_input and end_street and end_street_number and end_city and end_country and total_distance_km > 0:
        with st.container(border=True):
            try:
            # Generate the map
                m = folium.Map(location=[start_coords[1], start_coords[0]], zoom_start=15)
                folium.PolyLine(
                    locations=[list(reversed(coord)) for coord in route['features'][0]['geometry']['coordinates']],
                    color="blue"
                ).add_to(m)
            
                map_html = m._repr_html_()
                st.components.v1.html(map_html, height=375, width=800)  # Larger map

            except Exception as e:
                st.error(f"Error displaying the map: {e}") 

    # Add a checkbox to toggle visibility of the log database, placed after the map section
    show_log = st.checkbox("Arată nomenclatorul de produse", value=False)
    

    if show_log:
        with st.container(border=True):
            # Show log database when checkbox is checked
            st.write("**Nomenclator produse:**")
            log_styled = log.style.hide(axis="index")
            st.dataframe(log)
