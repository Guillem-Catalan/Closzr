-- #56: Add currency columns for Mexico MXN→EUR conversion
ALTER TABLE deals ADD COLUMN IF NOT EXISTS amount_in_home_currency NUMERIC;
ALTER TABLE deals ADD COLUMN IF NOT EXISTS deal_currency_code TEXT;
