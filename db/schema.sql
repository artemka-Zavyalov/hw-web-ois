CREATE EXTENSION IF NOT EXISTS btree_gist;

CREATE TABLE users (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    email           text NOT NULL,
    full_name       text NOT NULL,
    password_hash   text NOT NULL,
    role            text NOT NULL DEFAULT 'student'
        CHECK (role IN ('student', 'organizer', 'admin')),
    is_active       boolean NOT NULL DEFAULT true,
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX users_email_key ON users (lower(email));

CREATE TABLE clubs (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL UNIQUE,
    slug            text NOT NULL UNIQUE,
    description     text NOT NULL DEFAULT ''
);

CREATE TABLE club_organizers (
    user_id         bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    club_id         bigint NOT NULL REFERENCES clubs (id) ON DELETE CASCADE,
    PRIMARY KEY (user_id, club_id)
);

CREATE TABLE rooms (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name            text NOT NULL UNIQUE,
    building        text NOT NULL,
    capacity        integer NOT NULL CHECK (capacity > 0)
);

CREATE TABLE events (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    club_id         bigint NOT NULL REFERENCES clubs (id),
    room_id         bigint NOT NULL REFERENCES rooms (id),
    created_by      bigint NOT NULL REFERENCES users (id),
    title           text NOT NULL CHECK (length(title) BETWEEN 3 AND 200),
    description     text NOT NULL DEFAULT '',
    starts_at       timestamptz NOT NULL,
    ends_at         timestamptz NOT NULL,
    capacity        integer NOT NULL CHECK (capacity > 0),
    status          text NOT NULL DEFAULT 'pending'
        CHECK (status IN ('pending', 'published', 'rejected', 'cancelled')),
    reject_reason   text,
    cover_url       text,
    created_at      timestamptz NOT NULL DEFAULT now(),

    CONSTRAINT events_time_order CHECK (ends_at > starts_at)
);

CREATE INDEX events_starts_at_idx ON events (starts_at);
CREATE INDEX events_ends_at_idx ON events (ends_at);

CREATE TABLE registrations (
    id              bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id        bigint NOT NULL REFERENCES events (id) ON DELETE CASCADE,
    user_id         bigint NOT NULL REFERENCES users (id) ON DELETE CASCADE,
    status          text NOT NULL DEFAULT 'active' CHECK (status IN ('active', 'cancelled')),
    created_at      timestamptz NOT NULL DEFAULT now()
);

CREATE UNIQUE INDEX registrations_one_active on registrations (event_id, user_id)
    WHERE status = 'active';

CREATE TABLE tags (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    name        text NOT NULL UNIQUE
);

CREATE TABLE event_tags (
    event_id    bigint NOT NULL,
    tag_id      bigint NOT NULL,
    CONSTRAINT event_tags_event_fk
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT event_tags_tag_fk
        FOREIGN KEY (tag_id) REFERENCES tags (id) ON DELETE CASCADE,
    CONSTRAINT event_tags_event_tag_uq
        UNIQUE (event_id, tag_id)
);

CREATE TABLE reviews (
    id          bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    event_id    bigint NOT NULL,
    user_id     bigint NOT NULL,
    rating      integer NOT NULL,
    text        text,
    created_at  timestamptz NOT NULL DEFAULT now(),
    CONSTRAINT reviews_event_fk
        FOREIGN KEY (event_id) REFERENCES events (id) ON DELETE CASCADE,
    CONSTRAINT reviews_user_fk
        FOREIGN KEY (user_id) REFERENCES users (id) ON DELETE CASCADE,
    CONSTRAINT reviews_rating_range_chk
        CHECK (rating BETWEEN 1 AND 5),
    CONSTRAINT reviews_event_user_uq
        UNIQUE (event_id, user_id)
);
