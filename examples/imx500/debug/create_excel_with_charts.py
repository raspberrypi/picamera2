"""
convert json outputs of fps_auto.py to excel with charts - "all" mode
"""

import argparse
import json
import pandas as pd


def custom_round(val):
    if val % 1 < 0.1:
        return int(val)
    elif val % 1 >= 0.8:
        return round(val)
    else:
        return round(val, 2)


def create_excel_with_charts(json_path, excel_path):
    # Load JSON data
    with open(json_path, 'r') as file:
        data = json.load(file)

    # Extract data and create a DataFrame
    records = []
    for network, values in data.items():
        for fps, details in values.items():
            record = {
                "network": network,
                "user_fps": details["user_fps"],
                "dnn_runtime": round(details["dnn_runtime"], 2) if details['dnn_runtime'] != "NA" else "NA",
                "dsp_runtime": round(details["dsp_runtime"], 2) if details['dsp_runtime'] != "NA" else "NA",
                "fps": custom_round(float(details["fps"])),
                "dps": custom_round(float(details["dps"])),
                "detection": details["d"]
            }
            records.append(record)

    df = pd.DataFrame(records)

    # Save DataFrame to Excel with charts
    with pd.ExcelWriter(excel_path, engine='xlsxwriter') as writer:
        df.to_excel(writer, sheet_name='Data', index=False)
        workbook = writer.book

        # Create a new worksheet for charts
        chart_sheet = workbook.add_worksheet('Charts')

        # Create a chart for DNN Runtime
        chart1 = workbook.add_chart({'type': 'line'})
        for network in df['network'].unique():
            idx = df[df['network'] == network].index
            chart1.add_series({
                'name': network,
                'categories': ['Data', idx[0] + 1, 1, idx[-1] + 1, 1],
                'values': ['Data', idx[0] + 1, 2, idx[-1] + 1, 2],
            })
        chart1.set_title({'name': 'DNN Runtime vs User FPS'})
        chart1.set_x_axis({'name': 'User FPS'})
        chart1.set_y_axis({'name': 'DNN Runtime'})
        chart_sheet.insert_chart('A1', chart1)

        # Create a chart for DSP Runtime
        chart2 = workbook.add_chart({'type': 'line'})
        for network in df['network'].unique():
            idx = df[df['network'] == network].index
            chart2.add_series({
                'name': network,
                'categories': ['Data', idx[0] + 1, 1, idx[-1] + 1, 1],
                'values': ['Data', idx[0] + 1, 3, idx[-1] + 1, 3],
            })
        chart2.set_title({'name': 'DSP Runtime vs User FPS'})
        chart2.set_x_axis({'name': 'User FPS'})
        chart2.set_y_axis({'name': 'DSP Runtime'})
        chart_sheet.insert_chart('A20', chart2)

        # Create a chart for FPS
        chart3 = workbook.add_chart({'type': 'line'})
        for network in df['network'].unique():
            idx = df[df['network'] == network].index
            chart3.add_series({
                'name': network,
                'categories': ['Data', idx[0] + 1, 1, idx[-1] + 1, 1],
                'values': ['Data', idx[0] + 1, 4, idx[-1] + 1, 4],
            })
        chart3.set_title({'name': 'FPS vs User FPS'})
        chart3.set_x_axis({'name': 'User FPS'})
        chart3.set_y_axis({'name': 'FPS'})
        chart_sheet.insert_chart('A39', chart3)

        # Create a chart for DPS
        chart4 = workbook.add_chart({'type': 'line'})
        for network in df['network'].unique():
            idx = df[df['network'] == network].index
            chart4.add_series({
                'name': network,
                'categories': ['Data', idx[0] + 1, 1, idx[-1] + 1, 1],
                'values': ['Data', idx[0] + 1, 5, idx[-1] + 1, 5],
            })
        chart4.set_title({'name': 'DPS vs User FPS'})
        chart4.set_x_axis({'name': 'User FPS'})
        chart4.set_y_axis({'name': 'DPS'})
        chart_sheet.insert_chart('A58', chart4)


if __name__ == '__main__':
    parser = argparse.ArgumentParser()
    parser.add_argument("--json_path", required=True, type=str, help="path to json file")
    args = parser.parse_args()
    excel_path = args.json_path.replace(".json", ".xlsx")
    create_excel_with_charts(args.json_path, excel_path)

