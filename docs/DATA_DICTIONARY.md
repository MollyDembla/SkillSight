# Data dictionary

| Field | Meaning | Unit / rule |
|---|---|---|
| `period` | Reporting month supplied for observation | `YYYY-MM` |
| `state`, `district` | Geographic labels supplied by source | Text; district boundary not implied |
| `sector` | Sector label supplied by source | Text |
| `occupation_code`, `occupation_title` | Source classification identifier and title | Text; demo codes are not NCO mappings |
| `demand_count` | Source demand indicator | Nonnegative integer; source-specific proxy, not universally comparable |
| `training_seats` | Source training capacity indicator | Nonnegative integer; latest period used for snapshot |
| `quality_note` | Caveat attached to observation | Text |
| `source_id` | Provenance link | Foreign key to source registry |

Source registry fields: `name`, `source_type` (`synthetic_demo` or `imported`), `access_method`, `is_synthetic`, `imported_at`, `reporting_note`. Imported records do not establish a government source unless uploader provenance does so. Missing workforce supply, completions, certifications, placements, skills, qualifications, cost schedules, and NCO mappings are unavailable rather than inferred.
