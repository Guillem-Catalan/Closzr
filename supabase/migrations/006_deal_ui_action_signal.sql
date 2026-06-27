-- Add action_signal column to deal_ui
-- Short, clean action text (from Claude's action_signal).
-- Used in pipeline table view. Separate from action_headline (long, detailed).
ALTER TABLE deal_ui ADD COLUMN IF NOT EXISTS action_signal TEXT;
