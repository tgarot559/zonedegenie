-- Votre Zone de Génie — cartes cadeaux. PostgreSQL / Neon.
-- Chaque paiement Mollie possède une référence unique et une seule carte.
CREATE TABLE IF NOT EXISTS gift_orders (
  id UUID PRIMARY KEY,
  mollie_payment_id TEXT UNIQUE,
  buyer_email TEXT NOT NULL,
  recipient_email TEXT,
  recipient_name TEXT,
  amount_cents INTEGER NOT NULL DEFAULT 9000 CHECK (amount_cents = 9000),
  currency CHAR(3) NOT NULL DEFAULT 'EUR' CHECK (currency = 'EUR'),
  status TEXT NOT NULL DEFAULT 'pending' CHECK (status IN ('pending','paid','failed','canceled','expired','refunded')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  paid_at TIMESTAMPTZ
);
CREATE TABLE IF NOT EXISTS gift_cards (
  id UUID PRIMARY KEY,
  order_id UUID NOT NULL UNIQUE REFERENCES gift_orders(id),
  code_hash CHAR(64) NOT NULL UNIQUE,
  status TEXT NOT NULL DEFAULT 'active' CHECK (status IN ('active','reserved','redeemed','revoked')),
  created_at TIMESTAMPTZ NOT NULL DEFAULT now(),
  redeemed_at TIMESTAMPTZ,
  cal_booking_uid TEXT UNIQUE,
  CHECK ((status = 'redeemed') = (redeemed_at IS NOT NULL))
);
CREATE INDEX IF NOT EXISTS idx_gift_orders_status ON gift_orders(status);
-- Atomic redemption must check status='active' and update in one SQL transaction.
-- Never expose code_hash, connection strings, or buyer addresses to the public client.
