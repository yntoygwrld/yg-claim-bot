-- Bot Settings Table
-- Stores runtime configuration that can be changed without redeployment

CREATE TABLE IF NOT EXISTS bot_settings (
    id INTEGER PRIMARY KEY DEFAULT 1 CHECK (id = 1),  -- Singleton row
    claims_enabled BOOLEAN DEFAULT TRUE,
    max_claims_per_day INTEGER DEFAULT 1,
    maintenance_mode BOOLEAN DEFAULT FALSE,
    maintenance_message TEXT DEFAULT '🔧 Bot is under maintenance. Please check back soon!',
    announcement TEXT DEFAULT '',
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- Insert default settings if not exists
INSERT INTO bot_settings (id)
VALUES (1)
ON CONFLICT (id) DO NOTHING;

-- Create function to auto-update updated_at timestamp
CREATE OR REPLACE FUNCTION update_bot_settings_timestamp()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ LANGUAGE plpgsql;

-- Create trigger for auto-updating timestamp
DROP TRIGGER IF EXISTS bot_settings_updated_at ON bot_settings;
CREATE TRIGGER bot_settings_updated_at
    BEFORE UPDATE ON bot_settings
    FOR EACH ROW
    EXECUTE FUNCTION update_bot_settings_timestamp();

-- Enable RLS but allow service role full access
ALTER TABLE bot_settings ENABLE ROW LEVEL SECURITY;

-- Policy for service role (used by bot)
CREATE POLICY "Service role can manage bot_settings"
    ON bot_settings
    FOR ALL
    USING (auth.role() = 'service_role')
    WITH CHECK (auth.role() = 'service_role');

-- Policy for authenticated users (read-only for potential admin dashboard)
CREATE POLICY "Authenticated users can view bot_settings"
    ON bot_settings
    FOR SELECT
    USING (auth.role() = 'authenticated');
