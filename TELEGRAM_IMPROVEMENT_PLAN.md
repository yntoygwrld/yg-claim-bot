# Telegram Bot Improvement Plan

## Overview
This document outlines improvements to the YG Claim Bot submission flow, point system, and URL validation.

---

## 1. Point System Changes

### Current System
| Action | Points |
|--------|--------|
| Claim video | +10 |
| Submit link | +15 |
| **Total possible** | **25** |

### New System
| Action | Points |
|--------|--------|
| Claim video | +5 |
| Submit Instagram link | +10 |
| Submit TikTok link | +10 |
| Submit Twitter/X link | +10 |
| **Total possible** | **35** |

**Rationale:** Incentivize posting to MULTIPLE platforms. More platforms = more exposure = more points.

---

## 2. Improved URL Patterns (Research-Based)

### Current Patterns (config.py)
```python
URL_PATTERNS = {
    "tiktok": r"(www\.)?(tiktok\.com/@[\w\.]+/video/\d+|(vm|vt)\.tiktok\.com/[\w]+)",
    "instagram": r"(www\.)?instagram\.com/(p|reel|reels)/[\w-]+",
    "twitter": r"(www\.|mobile\.)?(twitter|x)\.com/\w+/status/\d+",
}
```

### Improved Patterns
```python
URL_PATTERNS = {
    # TikTok: Full URLs, short URLs (vm.tiktok, vt.tiktok), mobile URLs
    # Sources: regex101.com, Stack Overflow
    "tiktok": r"(?:https?://)?(?:www\.|m\.|vm\.|vt\.)?tiktok\.com/(?:@[\w.-]+/video/\d+|[\w]+/?)",

    # Instagram: Posts (/p/), Reels (/reel/, /reels/), optional www, trailing slash
    # Sources: regex101.com, codex.so
    "instagram": r"(?:https?://)?(?:www\.)?instagram\.com/(?:p|reel|reels)/[\w-]+/?",

    # Twitter/X: Both domains, optional www/mobile, video suffix supported
    # Sources: Stack Overflow, arkleseizure.net
    "twitter": r"(?:https?://)?(?:www\.|mobile\.)?(?:twitter|x)\.com/\w+/status(?:es)?/\d+(?:/video/\d+)?/?",
}
```

### URL Examples by Platform

**TikTok:**
- `https://www.tiktok.com/@username/video/1234567890123456789`
- `https://tiktok.com/@user.name/video/1234567890123456789`
- `https://vm.tiktok.com/ZMhABC123/`
- `https://vt.tiktok.com/ZSd9xyzAB/`
- `https://m.tiktok.com/v/1234567890.html`

**Instagram:**
- `https://www.instagram.com/reel/ABC123xyz_-/`
- `https://instagram.com/reel/ABC123xyz/`
- `https://www.instagram.com/p/ABC123xyz/`
- `https://instagram.com/reels/ABC123xyz_-/`

**Twitter/X:**
- `https://twitter.com/username/status/1234567890123456789`
- `https://x.com/username/status/1234567890123456789`
- `https://twitter.com/user/status/123456789/video/1`
- `https://www.x.com/user/statuses/123456789`
- `https://mobile.twitter.com/user/status/123456789`

---

## 3. New Submission Flow (Button-Based)

### After /claim - Show Submit Buttons
```
Here's your daily video, Gentleman! (+5 points)

[Video file attached]

Post this video and earn more points!

[Submit TikTok Link +10 PTS]
[Submit Instagram Link +10 PTS]
[Submit Twitter/X Link +10 PTS]
```

### After First Submission - Show "Submit More" Prompt
```
Submitted to TikTok! +10 points

Want to earn more? Post to other platforms:

[Submit Instagram Link +10 PTS]
[Submit Twitter/X Link +10 PTS]

Or type /mystats to see your score
```

### After All Three Submissions
```
Amazing! You've posted to all platforms!

Today's earnings: +35 points total
- Claim: +5 pts
- TikTok: +10 pts
- Instagram: +10 pts
- Twitter/X: +10 pts

See you tomorrow for another video!
```

### When User Tries /claim Again (Already Claimed)
```
You've already claimed today's video!

To maximize your points, submit your post links:

[Submit TikTok Link +10 PTS]
[Submit Instagram Link +10 PTS]
[Submit Twitter/X Link +10 PTS]

Come back tomorrow for a fresh video.
```

---

## 4. Database Changes Required

### Option A: Track per-claim submissions in reposts table (Current)
The current `reposts` table already tracks:
- `user_id` - Who submitted
- `video_id` - Which video
- `platform` - Which platform
- `post_url` - The URL
- `submitted_at` - When

**No schema changes needed** - we can query existing data to check which platforms user submitted for today's claim.

### Query to Check User's Submissions for Today
```sql
SELECT platform FROM reposts
WHERE user_id = 'xxx'
AND video_id = 'yyy'  -- today's claimed video
AND DATE(submitted_at) = CURRENT_DATE;
```

### New Database Function Needed
```python
async def get_user_submissions_for_video(user_id: str, video_id: str) -> List[str]:
    """Get list of platforms user has already submitted for a specific video."""
    result = supabase.table("reposts").select("platform").eq(
        "user_id", user_id
    ).eq("video_id", video_id).execute()
    return [r["platform"] for r in result.data] if result.data else []
```

---

## 5. Implementation Tasks

### Task 1: Update Point Values
- [ ] Change `increment_points` call in `create_claim` from 10 to 5
- [ ] Change `increment_points` call in `create_repost` from 15 to 10
- [ ] Update all user-facing messages to reflect new values

### Task 2: Update URL Patterns
- [ ] Replace URL_PATTERNS in config.py with improved regex
- [ ] Test all URL formats work correctly

### Task 3: Create Submit Buttons Flow
- [ ] Add inline keyboard buttons after video claim
- [ ] Create callback handlers for each platform button
- [ ] Implement conversation flow for link submission
- [ ] Track submissions per video to show remaining platforms

### Task 4: Update "Already Claimed" Message
- [ ] Check which platforms not yet submitted
- [ ] Show buttons for remaining platforms
- [ ] Encourage submission before next claim

### Task 5: Add Database Helper
- [ ] Add `get_user_submissions_for_video()` function
- [ ] Add `get_remaining_platforms()` helper

### Task 6: Update /mystats
- [ ] Show breakdown: claims vs submissions
- [ ] Show today's activity summary

---

## 6. Code Changes Summary

### Files to Modify:
1. **config.py** - Update URL_PATTERNS, add POINTS constants
2. **database.py** - Add `get_user_submissions_for_video()` function
3. **bot.py** - Major changes:
   - Update `claim()` to show submit buttons
   - Add callback handlers for platform buttons
   - Update "already claimed" flow
   - Update point values in messages

### New Constants (config.py)
```python
# Points Configuration
POINTS_CLAIM = 5
POINTS_SUBMIT = 10  # Per platform

# Supported platforms for submission
SUPPORTED_PLATFORMS = ["tiktok", "instagram", "twitter"]
```

### New Callback Data Format
```
submit_tiktok    - User wants to submit TikTok link
submit_instagram - User wants to submit Instagram link
submit_twitter   - User wants to submit Twitter/X link
```

---

## 7. User Experience Flow

```
USER                          BOT
─────────────────────────────────────────────
/claim
                              Here's your video! (+5 pts)
                              [video file]

                              [Submit TikTok +10 PTS]
                              [Submit Instagram +10 PTS]
                              [Submit Twitter/X +10 PTS]

*taps TikTok button*
                              Send your TikTok link:

*sends URL*
                              TikTok submitted! +10 pts

                              Want more points?
                              [Submit Instagram +10 PTS]
                              [Submit Twitter/X +10 PTS]

*taps Instagram button*
                              Send your Instagram link:

*sends URL*
                              Instagram submitted! +10 pts

                              One more platform available:
                              [Submit Twitter/X +10 PTS]

/claim (next day)
                              Here's your video! (+5 pts)
                              ...
```

---

## 8. Sources

- [TikTok URL Regex - Stack Overflow](https://stackoverflow.com/questions/74077377/regular-expression-to-match-any-tiktok-video-id-and-url)
- [TikTok Video ID Regex - regex101](https://regex101.com/library/D2hDie)
- [Instagram post/reel Regex - regex101](https://regex101.com/library/1dZHMi)
- [Instagram Regex - codex.so](https://codex.so/regex-for-instagram-posts)
- [Twitter Status URL Regex - Stack Overflow](https://stackoverflow.com/questions/4138483/twitter-status-url-regex)
- [X.com URL Pattern - Stack Overflow](https://stackoverflow.com/questions/77205116/link-validation-pattern-for-x-formerly-twitter)

---

## 9. Priority Order

1. **HIGH** - Update point system (5 claim / 10 submit)
2. **HIGH** - Button-based submission flow after claim
3. **MEDIUM** - Improved URL patterns
4. **MEDIUM** - "Already claimed" → show submit buttons
5. **LOW** - Enhanced /mystats breakdown

---

## 10. Estimated Effort

| Task | Complexity | Est. Time |
|------|------------|-----------|
| Point system update | Low | 10 min |
| URL patterns update | Low | 10 min |
| Submit buttons flow | High | 45 min |
| Callback handlers | Medium | 30 min |
| Database helper | Low | 10 min |
| Testing | Medium | 20 min |
| **Total** | | **~2 hours** |

---

## Ready for Implementation?

This plan covers all requested improvements:
- 5 points for claim, 10 points per platform submission
- Button-based submission for each platform with "+10 PTS" labels
- "Submit more?" flow after first submission
- Improved URL validation with research-backed patterns
- Database ready to track all submissions for leaderboard

**Approve to proceed with implementation.**
