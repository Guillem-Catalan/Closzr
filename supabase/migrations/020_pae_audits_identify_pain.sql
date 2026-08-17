-- Add MEDDIC "Identify Pain" pillar to pae_audits
ALTER TABLE pae_audits
  ADD COLUMN IF NOT EXISTS meddic_identify_pain_status     TEXT,
  ADD COLUMN IF NOT EXISTS meddic_identify_pain_confidence NUMERIC,
  ADD COLUMN IF NOT EXISTS meddic_identify_pain_evidence   TEXT;
