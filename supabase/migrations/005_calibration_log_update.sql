-- ============================================================================
-- Update calibration_log with date tracking and error classification
-- ============================================================================

ALTER TABLE calibration_log ADD COLUMN IF NOT EXISTS predicted_close_date DATE;
ALTER TABLE calibration_log ADD COLUMN IF NOT EXISTS predicted_confidence TEXT;
ALTER TABLE calibration_log ADD COLUMN IF NOT EXISTS actual_close_date DATE;
ALTER TABLE calibration_log ADD COLUMN IF NOT EXISTS days_off INTEGER;
ALTER TABLE calibration_log ADD COLUMN IF NOT EXISTS error_type TEXT;
