-- 1. Клубы и их афиша: каждый клуб и количество опубликованных мероприятий.
SELECT
    c.name,
    COUNT(e.id) AS published
FROM clubs c
LEFT JOIN events e
    ON e.club_id = c.id
   AND e.status = 'published'
GROUP BY c.id, c.name
ORDER BY published DESC, c.name;

-- 2. Организаторы и клубы, которые они ведут, одной строкой через запятую.
SELECT
    u.full_name,
    string_agg(c.name, ', ' ORDER BY c.name) AS clubs
FROM users u
JOIN club_organizers co ON co.user_id = u.id
JOIN clubs c ON c.id = co.club_id
WHERE u.role = 'organizer'
GROUP BY u.id, u.full_name
ORDER BY u.full_name;

-- 3. Активные студенты с двумя и более активными записями.
SELECT
    u.full_name,
    COUNT(r.id) AS count
FROM users u
JOIN registrations r
    ON r.user_id = u.id
   AND r.status = 'active'
WHERE u.role = 'student'
GROUP BY u.id, u.full_name
HAVING COUNT(r.id) >= 2
ORDER BY u.full_name;

-- 4. Загрузка аудиторий в ноябре 2026: часы занятости по модерации и публикациям.
SELECT
    r.name,
    COALESCE(
        ROUND(
            (
                SUM(
                    EXTRACT(
                        EPOCH FROM (
                            LEAST(e.ends_at, TIMESTAMPTZ '2026-12-01 00:00:00+07')
                            - GREATEST(e.starts_at, TIMESTAMPTZ '2026-11-01 00:00:00+07')
                        )
                    )
                ) / 3600
            )::numeric,
            2
        ),
        0.00
    ) AS hours
FROM rooms r
LEFT JOIN events e
    ON e.room_id = r.id
   AND e.status IN ('pending', 'published')
   AND e.starts_at < TIMESTAMPTZ '2026-12-01 00:00:00+07'
   AND e.ends_at > TIMESTAMPTZ '2026-11-01 00:00:00+07'
GROUP BY r.id, r.name
ORDER BY hours DESC, r.name;

-- 5. Мероприятия с тегом «IT», по времени начала.
SELECT
    e.title,
    e.starts_at
FROM events e
JOIN event_tags et ON et.event_id = e.id
JOIN tags t ON t.id = et.tag_id
WHERE t.name = 'IT'
ORDER BY e.starts_at;
