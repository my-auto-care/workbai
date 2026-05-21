import re

with open('/root/workbai/backend/app/api/sessions.py', 'r') as f:
    c = f.read()

# Add vehicle_mileage to SessionCreate
c = c.replace(
    '    vehicle_vin: Optional[str] = None',
    '    vehicle_vin: Optional[str] = None\n    vehicle_mileage: Optional[int] = None'
)

# Add vehicle_mileage to _session_dict
c = c.replace(
    '"vehicle_vin": s.vehicle_vin,',
    '"vehicle_vin": s.vehicle_vin,\n        "vehicle_mileage": s.vehicle_mileage,'
)

# Add vehicle_mileage to create_session
c = c.replace(
    '        vehicle_vin=body.vehicle_vin,',
    '        vehicle_vin=body.vehicle_vin,\n        vehicle_mileage=body.vehicle_mileage,'
)

with open('/root/workbai/backend/app/api/sessions.py', 'w') as f:
    f.write(c)
print('done')
