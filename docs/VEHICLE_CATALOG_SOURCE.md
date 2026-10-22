# Vehicle Catalog Source — Internal Check-in Reference

The internal rapid vehicle catalog uses the National Highway Traffic Safety Administration Product Information Catalog and Vehicle Listing API (vPIC) only as a **vehicle-identification reference**. The API documents model lookup by make and model year, as well as VIN decode endpoints. vPIC data is manufacturer-submitted vehicle-identification information and is rate-controlled by NHTSA.

For example, the importer requests the documented endpoint form:

```text
https://vpic.nhtsa.dot.gov/api/vehicles/GetModelsForMakeYear/make/{make}/modelyear/{year}?format=json
```

A live source check on 2026-10-22 confirmed the response includes `2017 Toyota Highlander` with source make ID `448` and model ID `2213`.

## Non-negotiable use boundary

A catalog match only fills a proposed year, make, and model for staff confirmation. It does **not** prove that the vehicle belongs to a customer, identify a specific VIN/trim/mileage, determine service history, establish recall applicability, generate an inspection item, or support a diagnostic, safety, maintenance, pricing, or repair claim.

The importer caches the source name, URL, source IDs, and retrieval timestamp for each catalog row. It does not run during Check-in, so a provider delay or error cannot interrupt manual intake. Staff can always use the manual entry fallback.

**Sources**

- NHTSA vPIC Vehicle API: https://vpic.nhtsa.dot.gov/api/
- NHTSA VIN Decoder: https://www.nhtsa.gov/vin-decoder
