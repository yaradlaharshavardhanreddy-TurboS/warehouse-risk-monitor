
def get_trend_analytics(conn):
    cur = conn.cursor()

    daily_alarms = cur.execute("""
        SELECT
            substr(detected_at, 1, 10) AS event_date,
            COUNT(*) AS alarm_count
        FROM alarms
        GROUP BY event_date
        ORDER BY event_date
    """).fetchall()

    daily_sensor_readings = cur.execute("""
        SELECT
            substr(recorded_at, 1, 10) AS reading_date,
            COUNT(*) AS reading_count,
            ROUND(AVG(temperature_c), 2) AS average_temperature,
            ROUND(MIN(temperature_c), 2) AS minimum_temperature,
            ROUND(MAX(temperature_c), 2) AS maximum_temperature,
            ROUND(AVG(humidity_pct), 2) AS average_humidity
        FROM sensor_readings
        GROUP BY reading_date
        ORDER BY reading_date
    """).fetchall()

    daily_door_events = cur.execute("""
        SELECT
            substr(event_timestamp, 1, 10) AS event_date,
            COUNT(*) AS event_count
        FROM door_events
        GROUP BY event_date
        ORDER BY event_date
    """).fetchall()

    daily_alarms_by_type = cur.execute("""
        SELECT
            substr(detected_at, 1, 10) AS event_date,
            alarm_type,
            COUNT(*) AS alarm_count
        FROM alarms
        GROUP BY event_date, alarm_type
        ORDER BY event_date, alarm_type
    """).fetchall()

    return {
        "daily_alarm_trends": [
            {
                "date": row[0],
                "alarm_count": row[1]
            }
            for row in daily_alarms
        ],
        "daily_sensor_trends": [
            {
                "date": row[0],
                "reading_count": row[1],
                "average_temperature": row[2],
                "minimum_temperature": row[3],
                "maximum_temperature": row[4],
                "average_humidity": row[5]
            }
            for row in daily_sensor_readings
        ],
        "daily_door_event_trends": [
            {
                "date": row[0],
                "event_count": row[1]
            }
            for row in daily_door_events
        ],
        "daily_alarm_type_trends": [
            {
                "date": row[0],
                "alarm_type": row[1],
                "alarm_count": row[2]
            }
            for row in daily_alarms_by_type
        ]
    }
