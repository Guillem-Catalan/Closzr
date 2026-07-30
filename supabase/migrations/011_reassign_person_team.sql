-- 011_reassign_person_team.sql
-- RPC called from the orgchart UI when a person changes team.
-- Updates the team field on all their active deals in both deals and deal_ui.

CREATE OR REPLACE FUNCTION reassign_person_team(person_email TEXT, new_team TEXT)
RETURNS void AS $$
BEGIN
  UPDATE deals SET team = new_team WHERE pae = person_email OR pbd = person_email;
  UPDATE deal_ui SET team = new_team WHERE pae = person_email OR pbd = person_email;
END;
$$ LANGUAGE plpgsql SECURITY DEFINER;
