-- BOM2Pic Database Setup for Supabase
-- Run this SQL in your Supabase SQL Editor

-- 1. Create users table (extends Supabase auth.users)
CREATE TABLE IF NOT EXISTS public.users (
    id UUID PRIMARY KEY REFERENCES auth.users(id) ON DELETE CASCADE,
    email TEXT NOT NULL,
    plan TEXT NOT NULL DEFAULT 'free' 
        CHECK (plan IN ('free', 'basic', 'pro', 'pro_plus')),
    stripe_customer_id TEXT,
    stripe_subscription_id TEXT,
    subscription_status TEXT DEFAULT 'inactive',
    enterprise_monthly_limit INT, -- Custom limit for enterprise (future)
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW()
);

-- 2. Create usage_monthly table for tracking image processing
CREATE TABLE IF NOT EXISTS public.usage_monthly (
    user_id UUID NOT NULL REFERENCES public.users(id) ON DELETE CASCADE,
    year_month TEXT NOT NULL, -- Format: "2024-01"
    images_processed INT DEFAULT 0,
    created_at TIMESTAMPTZ DEFAULT NOW(),
    updated_at TIMESTAMPTZ DEFAULT NOW(),
    PRIMARY KEY (user_id, year_month)
);

-- 3. Create RPC function for atomic usage increment
CREATE OR REPLACE FUNCTION public.increment_usage(
    p_user_id UUID, 
    p_year_month TEXT
) 
RETURNS VOID
LANGUAGE SQL
SECURITY DEFINER
AS $$
    INSERT INTO public.usage_monthly (user_id, year_month, images_processed)
    VALUES (p_user_id, p_year_month, 1)
    ON CONFLICT (user_id, year_month)
    DO UPDATE SET 
        images_processed = usage_monthly.images_processed + 1,
        updated_at = NOW();
$$;

-- 4. Enable Row Level Security (RLS)
ALTER TABLE public.users ENABLE ROW LEVEL SECURITY;
ALTER TABLE public.usage_monthly ENABLE ROW LEVEL SECURITY;

-- 5. Create RLS policies for users table
CREATE POLICY "Users can read their own data" ON public.users
    FOR SELECT USING (auth.uid() = id);

CREATE POLICY "Users can update their own data" ON public.users
    FOR UPDATE USING (auth.uid() = id);

-- 6. Create RLS policies for usage_monthly table
CREATE POLICY "Users can read their own usage" ON public.usage_monthly
    FOR SELECT USING (auth.uid() = user_id);

-- 7. Create indexes for performance
CREATE INDEX IF NOT EXISTS idx_users_email ON public.users(email);
CREATE INDEX IF NOT EXISTS idx_users_stripe_customer ON public.users(stripe_customer_id);
CREATE INDEX IF NOT EXISTS idx_usage_monthly_user_month ON public.usage_monthly(user_id, year_month);

-- 8. Create trigger to update updated_at timestamp
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = NOW();
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_users_updated_at 
    BEFORE UPDATE ON public.users
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_usage_updated_at 
    BEFORE UPDATE ON public.usage_monthly
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- 9. Grant necessary permissions (service role can do everything)
GRANT ALL ON public.users TO service_role;
GRANT ALL ON public.usage_monthly TO service_role;
GRANT EXECUTE ON FUNCTION public.increment_usage TO service_role;

-- 10. Insert some test data (optional)
-- This will be handled by the application when users sign up

COMMENT ON TABLE public.users IS 'User accounts with billing information';
COMMENT ON TABLE public.usage_monthly IS 'Monthly usage tracking for image processing';
COMMENT ON FUNCTION public.increment_usage IS 'Atomically increment user usage count';
