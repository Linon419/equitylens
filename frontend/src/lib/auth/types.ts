import type { Locale } from "@/lib/i18n";

export type AuthTokens = {
  access_token: string;
  refresh_token: string;
  token_type: "bearer";
  access_expires_in: number;
  refresh_expires_in: number;
};

export type AuthUser = {
  id: number;
  email: string;
  full_name: string | null;
  avatar_url: string | null;
  preferred_locale: Locale;
  created_at: string;
};

export type AuthResponse = AuthTokens & { user: AuthUser };
export type AuthError = { code: string; request_id: string };
