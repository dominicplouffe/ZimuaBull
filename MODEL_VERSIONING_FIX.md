# Model Versioning Fix

## Problem

The model filename constants (`MODEL_FILENAME` and `MODEL_METADATA_FILENAME`) were hard-coded with version numbers (e.g., `intraday_model_v2.joblib`), which caused issues when using the `--bump-version` flag in the `retrain_daytrading_model` command.

### Issues:
1. When bumping from v2 to v3, the constants file would be updated, but imported constants in other modules wouldn't reflect the change
2. The new v3 model would be saved with the old v2 filename, overwriting the previous model
3. Version tracking was inconsistent between feature versions and model filenames

## Solution

Made model filenames **dynamic** based on the feature version by:

1. **Adding helper functions in `constants.py`**:
   ```python
   def get_model_filename(version: str | None = None) -> str:
       """Get model filename for a specific version (defaults to current FEATURE_VERSION)."""
       ver = version or FEATURE_VERSION
       return f"intraday_model_{ver}.joblib"

   def get_model_metadata_filename(version: str | None = None) -> str:
       """Get model metadata filename for a specific version (defaults to current FEATURE_VERSION)."""
       ver = version or FEATURE_VERSION
       return f"intraday_model_{ver}_meta.json"
   ```

2. **Updated `save_model()` in `modeling.py`**:
   - Added `version` parameter (optional, defaults to current `FEATURE_VERSION`)
   - Uses `get_model_filename(version)` instead of hard-coded constant
   - Signature: `save_model(model, metrics, feature_columns, imputer, version=None)`

3. **Updated `load_model()` in `modeling.py`**:
   - Added `version` parameter (optional, defaults to current `FEATURE_VERSION`)
   - Uses `get_model_filename(version)` instead of hard-coded constant
   - Signature: `load_model(version=None)`

4. **Updated `retrain_daytrading_model` command**:
   - Passes `version` parameter to `save_model()` call (line 588)
   - Uses helper functions in `_upsert_existing_model_version()` (lines 755-756)
   - Uses helper functions in `_print_summary()` (line 852)

## Files Modified

1. **zimuabull/daytrading/constants.py**:
   - Added `get_model_filename()` function
   - Added `get_model_metadata_filename()` function
   - Kept original constants for backward compatibility

2. **zimuabull/daytrading/modeling.py**:
   - Updated `save_model()` to accept `version` parameter
   - Updated `load_model()` to accept `version` parameter
   - Changed imports to use helper functions

3. **zimuabull/management/commands/retrain_daytrading_model.py**:
   - Updated imports to use helper functions
   - Passes `version` to `save_model()` call
   - Uses helper functions throughout

## Usage Examples

### Saving a model with explicit version:
```python
from zimuabull.daytrading.modeling import save_model

# Save model for v3
save_path = save_model(model, metrics, feature_columns, imputer, version="v3")
# Saves to: artifacts/daytrading/intraday_model_v3.joblib
```

### Loading a specific version:
```python
from zimuabull.daytrading.modeling import load_model

# Load v2 model
model, feature_columns, imputer = load_model(version="v2")

# Load current version (default)
model, feature_columns, imputer = load_model()
```

### Version bumping now works correctly:
```bash
# Bump from v2 to v3 and retrain
python manage.py retrain_daytrading_model --bump-version

# Result:
# - constants.py updated: FEATURE_VERSION = "v3"
# - Old v2 model preserved as: intraday_model_v2.joblib
# - New v3 model saved as: intraday_model_v3.joblib
```

## Backward Compatibility

- The hard-coded constants (`MODEL_FILENAME`, `MODEL_METADATA_FILENAME`) are still defined for backward compatibility
- Code that doesn't specify a version will use the current `FEATURE_VERSION` (via helper functions)
- Existing code that uses `load_model()` without arguments continues to work

## Benefits

1. **Proper version isolation**: Each version gets its own model files
2. **No data loss**: Old models aren't overwritten when bumping versions
3. **Explicit version control**: Can save/load any version explicitly
4. **Cleaner architecture**: Version is a parameter, not hard-coded in filenames
5. **Future-proof**: Easy to support multiple model versions simultaneously

## Testing

Verified that:
- ✅ Helper functions generate correct filenames
- ✅ `save_model()` accepts version parameter
- ✅ `load_model()` accepts version parameter
- ✅ Command imports without errors
- ✅ Backward compatibility maintained

## Next Steps

When you're ready to bump to v3:
```bash
python manage.py retrain_daytrading_model --bump-version
```

This will:
1. Update `FEATURE_VERSION` from v2 to v3 in constants.py
2. Preserve existing v2 model files
3. Generate new features with v3 labels
4. Train new model and save as `intraday_model_v3.joblib`
5. Update metadata as `intraday_model_v3_meta.json`
