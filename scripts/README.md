Convert the source catalog from the repository root:

```sh
python scripts/convert_exercises.py
```

This writes `exercises.mongodb.json`, a JSON array matching the fields in
`backend/src/crosfit_training_backend/models/exercise.py`. The original
`exercises.json` is preserved. Custom paths can be passed with `--input` and
`--output`.

Mapping:

| Source | MongoDB document |
| --- | --- |
| `slug`, `name`, `modality` | Preserved; surrounding whitespace removed from `name` |
| Names, slug, abbreviation, curated aliases | Normalized phrases, words, word-boundary suffixes, punctuation variants and common abbreviations in `search_terms` |
| `equipment_type` | Split on commas, trimmed, lowercased, deduplicated into `equipment` |
| Curated annotations in `exercise_enrichment.py` | `movement_pattern` and `muscle_groups` |
| New catalog entry | `is_archived: false` |

Source IDs are omitted so MongoDB generates ObjectIds. `class_exercise`, `level`,
`video`, and `teaser` have no corresponding model fields and are omitted. The
source remains available for future enrichment. Updating an exercise's name
through the current API rebuilds `search_terms` from that name alone, removing
the imported aliases.

Annotation conventions:

- One primary pattern is stored because the model accepts only one. Squats,
  lunges and step-ups use `squat`; cleans, snatches and deadlifts use `hinge`;
  loaded walking uses `carry`. Rowing uses `pull` and running uses `locomotion`.
  Burpees, thrusters and clean-and-jerk combinations use `other` because they
  combine distinct patterns. Static trunk/bracing exercises use `core`.
- Muscle groups identify major working muscles and important stabilizers;
  they are catalog tags, not an exhaustive anatomical or activation ranking.
  The vocabulary is `biceps`, `calves`, `chest`, `core`, `forearms`, `glutes`,
  `hamstrings`, `hip_flexors`, `lats`, `lower_back`, `quads`, `shoulders`,
  `traps`, `triceps`, and `upper_back`. `core` groups the abdominal wall and
  obliques; `upper_back` groups rhomboids and other scapular stabilizers.
- Rest intentionally uses `other` and an empty muscle list. `tumbler-pull` has
  no source description, equipment or video; its `pull` classification and
  upper-body muscle tags are provisional, inferred from its name.
- Source categories are not used as classification rules. Each slug is
  explicitly annotated; unknown slugs cause conversion to fail for review.
  Modality, names, slugs and equipment are preserved. Three incorrect Ukrainian
  equipment translations are overridden only for search aliases.

The classifications are editorial choices informed by the source descriptions,
[CrossFit's movement library](https://www.crossfit.com/crossfit-movements),
[clean technique](https://www.crossfit.com/essentials/foundational-movement-clean-what-is-a-clean),
[snatch technique](https://www.crossfit.com/essentials/the-snatch), and
[Concept2 SkiErg technique](https://www.concept2.co.uk/training/skierg-technique).
Those sources describe movements; they do not define this application's tags.

Search terms are built for the API's existing anchored prefix query. For example,
`Hang Power Clean` includes `power clean`, and pull-ups include `pull-up`,
`pull up`, `pullup`, and plural variants. DB/KB variants, corrected spellings,
common abbreviations, and Ukrainian names are included. Standalone function
words and punctuation-only terms are excluded. Character-by-character prefixes,
HTML descriptions, muscle names and broad source categories are not indexed.
The backend still returns at most ten alphabetically sorted matches; the data
does not change ranking or query normalization.

Run catalog and search regression checks without installing dependencies:

```sh
python -B -m unittest discover -s scripts -p 'test_*.py'
```

Docker Compose seeds the validated catalog automatically:

```sh
docker compose up -d --build
docker compose logs mongo-seed
```

The `mongo-seed` service waits for MongoDB's healthcheck, validates the complete
file against the backend schema, creates the exercise indexes and inserts
missing slugs into the `exercises` collection. It exits successfully after
seeding. A successful log reports `233 inserted, 0 already present` for an empty
database. Existing slugs are preserved, including IDs, edits and archived status.
Repeated starts do not duplicate entries; existing volumes do not need deleting.
`MONGO_DB_NAME` can be set in the root `.env` file (default: `crossfit`). Inside
Compose, the seed service connects to `mongodb://mongo:27017`.

The catalog is packaged into the seed image. After changing it, rebuild and run
the seed service explicitly:

```sh
docker compose build mongo-seed
docker compose run --rm mongo-seed
```

If an application service is added to Compose, make it depend on `mongo-seed`
with `condition: service_completed_successfully` so it starts after seeding.
This follows [Compose's startup dependency behavior](https://docs.docker.com/compose/how-tos/startup-order/).
Plain `docker compose up mongo` starts only MongoDB; use `docker compose up`
or explicitly run `mongo-seed` to seed it.

The script can also run locally with a root virtual environment:

```sh
UV_PROJECT_ENVIRONMENT="$PWD/.venv" uv sync --project backend --locked --group dev
.venv/bin/python scripts/seed_exercises.py --validate-only
MONGO_URL=mongodb://localhost:27017 MONGO_DB_NAME=crossfit \
  .venv/bin/python scripts/seed_exercises.py
```

Use `--file PATH` to select a different catalog. The script reads `MONGO_URL`
and `MONGO_DB_NAME` from environment variables; for local execution, export
them explicitly (it does not load `.env` itself). Invalid input causes a nonzero
exit before connecting to MongoDB. Database/index failures also cause a nonzero
exit; after a partial database failure it is safe to rerun. Insert-only upserts
use MongoDB's [`$setOnInsert`](https://www.mongodb.com/docs/manual/reference/operator/update/setoninsert/).

For a deliberate replacement of existing catalog entries, MongoDB Database
Tools can instead import the file directly:

```sh
mongoimport --uri mongodb://localhost:27017/crossfit \
  --collection exercises --file exercises.mongodb.json --jsonArray \
  --mode upsert --upsertFields slug
```

This inserts new slugs and replaces documents with matching slugs, preserving
their existing `_id`. Reimporting therefore resets those exercises to the values
in the file, including `is_archived`. Change the URI for a different database.
The backend creates the model's indexes when it initializes its database.
