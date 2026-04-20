"""Presets API — scene, persona, content-set, video, negative-prompt presets + LoRA discovery."""
from __future__ import annotations

from pathlib import Path

from fastapi import APIRouter

router = APIRouter(tags=["presets"])

# ═══════════════════════════════════════════════════════════════════════
# Scene Presets
# ═══════════════════════════════════════════════════════════════════════

SCENE_PRESETS = [
    {"id": "glamour_bedroom", "label": "Glamour — Bedroom", "prompt": "luxury bedroom, silk sheets, warm golden hour lighting, sensual pose, professional boudoir photography, shallow depth of field, 85mm lens"},
    {"id": "glamour_studio", "label": "Glamour — Studio", "prompt": "professional photo studio, soft rim lighting, white backdrop, elegant pose, beauty photography, high fashion, 50mm portrait lens"},
    {"id": "lingerie_editorial", "label": "Lingerie Editorial", "prompt": "wearing lace lingerie, editorial fashion shoot, soft diffused lighting, luxury apartment interior, elegant, alluring gaze, magazine quality"},
    {"id": "bikini_poolside", "label": "Bikini — Pool", "prompt": "wearing bikini, poolside, tropical resort, bright sunlight, wet skin, reflections in water, summer vibes, lifestyle photography"},
    {"id": "bikini_beach", "label": "Bikini — Beach", "prompt": "wearing bikini, sandy beach, ocean waves, golden sunset, wind in hair, candid pose, vacation lifestyle photography"},
    {"id": "fitness_gym", "label": "Fitness — Gym", "prompt": "wearing sports bra and leggings, modern gym, dramatic lighting, athletic pose, toned body, fitness photography, strong and confident"},
    {"id": "casual_streetwear", "label": "Casual — Street", "prompt": "casual streetwear outfit, urban city background, golden hour, candid walking pose, trendy fashion, natural makeup, lifestyle photography"},
    {"id": "elegant_evening", "label": "Elegant — Evening", "prompt": "wearing elegant evening dress, upscale restaurant or rooftop bar, city lights bokeh, sophisticated pose, glamorous makeup, cinematic lighting"},
    {"id": "cosplay_fantasy", "label": "Cosplay — Fantasy", "prompt": "fantasy cosplay outfit, dramatic theatrical lighting, enchanted forest or castle background, powerful pose, detailed costume, cinematic composition"},
    {"id": "artistic_bw", "label": "Artistic — B&W", "prompt": "black and white photography, dramatic shadows, nude art style, sculptural pose, fine art photography, high contrast, tasteful and artistic"},
    {"id": "selfie_mirror", "label": "Selfie — Mirror", "prompt": "mirror selfie, casual outfit, modern apartment, natural light from window, relaxed pose, smartphone in hand, authentic social media aesthetic"},
    {"id": "bathtime", "label": "Bath Time", "prompt": "luxury bathtub, candles, rose petals, steam, soft warm lighting, relaxing pose, spa aesthetic, intimate atmosphere, beauty photography"},
    {"id": "morning_bed", "label": "Morning in Bed", "prompt": "laying in white bedsheets, morning sunlight through sheer curtains, messy hair, sleepy smile, natural no-makeup look, cozy bedroom, warm tones, intimate candid photography"},
    {"id": "silk_robe", "label": "Silk Robe", "prompt": "wearing silk robe loosely draped, sitting on edge of bed, soft window light, elegant boudoir, satin pillows, relaxed confident pose, warm color palette, intimate portrait"},
    {"id": "lace_closeup", "label": "Lace Close-Up", "prompt": "wearing delicate lace bodysuit, close-up portrait, soft studio lighting, shallow depth of field, detailed skin texture, sultry eye contact, beauty retouching, 85mm macro"},
    {"id": "coffee_shop", "label": "Coffee Shop Date", "prompt": "sitting in trendy coffee shop, holding latte, casual chic outfit, warm ambient lighting, exposed brick background, candid laugh, lifestyle photography, bokeh background"},
    {"id": "rooftop_sunset", "label": "Rooftop Sunset", "prompt": "standing on city rooftop at golden hour, wind blowing hair, wearing summer dress, skyline in background, warm orange and pink tones, cinematic wide angle, lifestyle influencer"},
    {"id": "car_selfie", "label": "Car Selfie", "prompt": "sitting in luxury car front seat, selfie angle, designer sunglasses on head, casual crop top, natural daylight, confident smirk, steering wheel visible, social media aesthetic"},
    {"id": "brunch_aesthetic", "label": "Brunch Aesthetic", "prompt": "sitting at outdoor brunch table, fresh pastries and mimosas, wearing sundress, wide brim hat, bright natural daylight, colorful food flat lay, influencer lifestyle photo"},
    {"id": "yacht_luxury", "label": "Yacht Life", "prompt": "on luxury yacht deck, wearing white one-piece swimsuit, turquoise ocean water, bright sun, tanned skin, wind in hair, sunglasses, champagne glass, aspirational lifestyle"},
    {"id": "tropical_shower", "label": "Tropical Shower", "prompt": "outdoor tropical rain shower, wet hair and skin, wearing bikini, lush green jungle background, water droplets on body, golden hour backlight, exotic paradise"},
    {"id": "hotel_balcony", "label": "Hotel Balcony", "prompt": "standing on luxury hotel balcony, wearing sheer cover-up over bikini, ocean view, morning light, leaning on railing, resort vacation vibes, travel photography"},
    {"id": "red_carpet", "label": "Red Carpet Glam", "prompt": "wearing tight designer gown, red carpet event, camera flashes, full glam makeup, diamond jewelry, confident power pose, paparazzi style photography, celebrity aesthetic"},
    {"id": "wet_look", "label": "Wet Look", "prompt": "wet hair slicked back, water droplets on skin, dark moody studio lighting, wearing minimal clothing, glistening skin, editorial fashion photography, dramatic shadows"},
    {"id": "leather_edgy", "label": "Leather & Edgy", "prompt": "wearing black leather outfit, dark urban alley, neon light reflections, edgy confident pose, smokey eye makeup, industrial backdrop, high contrast photography, rebellious aesthetic"},
    {"id": "sheer_dress", "label": "Sheer Dress", "prompt": "wearing flowing sheer fabric dress, backlit by golden sunlight, silhouette visible, outdoor field of flowers, ethereal dreamy aesthetic, wind movement, fine art fashion photography"},
    {"id": "yoga_pose", "label": "Yoga Session", "prompt": "doing yoga pose on mat, wearing sports bra and yoga pants, bright minimalist studio, natural light, toned flexible body, zen focused expression, wellness lifestyle"},
    {"id": "post_workout", "label": "Post Workout", "prompt": "post-workout selfie in gym mirror, light sweat glistening, wearing crop top and shorts, toned abs visible, gym equipment background, confident smile, fitness motivation"},
    {"id": "running_outdoor", "label": "Running Outdoors", "prompt": "jogging on scenic trail, wearing athletic outfit, ponytail bouncing, morning golden light, trees and nature background, dynamic action pose, healthy active lifestyle photography"},
    {"id": "nightclub", "label": "Nightclub Vibes", "prompt": "in upscale nightclub, wearing tight mini dress, colorful neon and disco lights, dancing pose, glitter makeup, VIP booth background, nightlife photography, vibrant energy"},
    {"id": "wine_evening", "label": "Wine Evening", "prompt": "lounging on velvet couch, holding glass of red wine, wearing silky slip dress, dim moody candlelight, luxury living room, legs crossed, seductive glance, intimate atmosphere"},
    {"id": "angel_wings", "label": "Angel Wings", "prompt": "wearing white lingerie with large white angel wings, ethereal studio lighting, fog machine haze, heavenly glow, feathers, divine pose, fantasy themed photoshoot"},
    {"id": "oil_painting", "label": "Oil Painting Style", "prompt": "classical oil painting style portrait, Renaissance lighting, draped fabric, rich warm color palette, painterly brushstrokes, masterpiece quality, timeless beauty, museum worthy"},
    {"id": "neon_glow", "label": "Neon Glow", "prompt": "colorful neon lights casting pink and blue glow on skin, dark background, cyberpunk aesthetic, wearing futuristic outfit, dramatic color contrast, creative portrait photography"},
    {"id": "shower_steam", "label": "Steamy Shower", "prompt": "in glass shower, steam filling the space, water running down body, frosted glass, warm bathroom lighting, tasteful angles, wet hair, sensual atmosphere, spa photography"},
]

# ═══════════════════════════════════════════════════════════════════════
# Content Set Presets
# ═══════════════════════════════════════════════════════════════════════

CONTENT_SET_PRESETS = [
    {"id": "beach_day", "label": "Beach Day", "name": "Beach Day Series", "prompt": "sandy beach, ocean waves, bright sunlight, wearing bikini, summer vibes, golden hour", "set_size": 6, "description": "Sun-soaked beach content from morning to sunset"},
    {"id": "city_girl", "label": "City Girl", "name": "City Girl Series", "prompt": "urban city streets, modern architecture, trendy outfit, street style photography, golden hour, candid poses", "set_size": 6, "description": "Stylish city exploration shoot across iconic urban spots"},
    {"id": "spa_day", "label": "Spa Day", "name": "Spa & Self-Care", "prompt": "luxury spa setting, soft towels, candles, relaxing atmosphere, natural beauty, warm tones, wellness aesthetic", "set_size": 4, "description": "Relaxation and self-care themed content set"},
    {"id": "lazy_sunday", "label": "Lazy Sunday", "name": "Lazy Sunday", "prompt": "cozy bedroom, oversized shirt, morning sunlight, coffee in bed, relaxed natural look, intimate candid photography", "set_size": 4, "description": "Cozy morning-in-bed casual content"},
    {"id": "lingerie_editorial_set", "label": "Lingerie Editorial", "name": "Lingerie Editorial Set", "prompt": "wearing lace lingerie, soft studio lighting, luxury interior, editorial fashion photography, elegant poses, boudoir", "set_size": 6, "description": "High-end lingerie editorial across multiple looks"},
    {"id": "streetwear_drop", "label": "Streetwear Drop", "name": "Streetwear Lookbook", "prompt": "trendy streetwear outfit, urban backdrop, graffiti walls, sneakers, oversized jacket, confident attitude, lifestyle photography", "set_size": 4, "description": "Street fashion lookbook for social media"},
    {"id": "red_carpet_set", "label": "Red Carpet Glam", "name": "Red Carpet Collection", "prompt": "wearing designer gown, glamorous makeup, diamond jewelry, red carpet backdrop, camera flashes, celebrity photography", "set_size": 4, "description": "Full glam event-ready looks"},
    {"id": "athleisure", "label": "Athleisure", "name": "Athleisure Collection", "prompt": "wearing sports bra and leggings, modern gym, athletic poses, toned body, fitness lifestyle, bright clean lighting", "set_size": 6, "description": "Fitness and activewear lifestyle set"},
    {"id": "tropical_getaway", "label": "Tropical Getaway", "name": "Tropical Getaway", "prompt": "tropical paradise, palm trees, turquoise water, wearing swimsuit, resort setting, vacation vibes, travel photography", "set_size": 6, "description": "Dream vacation tropical content bundle"},
    {"id": "yacht_party", "label": "Yacht Party", "name": "Yacht Life Series", "prompt": "on luxury yacht, ocean backdrop, wearing white swimsuit, champagne, tanned skin, aspirational lifestyle photography", "set_size": 4, "description": "Luxury yacht lifestyle content"},
    {"id": "hotel_staycation", "label": "Hotel Staycation", "name": "Hotel Room Series", "prompt": "luxury hotel room, white robe, room service, city view from window, elegant interior, travel influencer photography", "set_size": 4, "description": "Upscale hotel room content set"},
    {"id": "golden_hour", "label": "Golden Hour Magic", "name": "Golden Hour Collection", "prompt": "golden hour sunset lighting, outdoor field, flowing dress, warm orange and pink tones, backlit silhouette, dreamy ethereal", "set_size": 6, "description": "Golden hour magic across multiple outdoor scenes"},
    {"id": "night_out", "label": "Night Out", "name": "Night Out Series", "prompt": "nightclub or upscale bar, neon lights, wearing tight dress, cocktail, smokey eye makeup, nightlife photography, vibrant energy", "set_size": 4, "description": "Night life and party content"},
    {"id": "pool_party", "label": "Pool Party", "name": "Pool Party Set", "prompt": "poolside, tropical resort, wearing bikini, wet skin, bright sunlight, reflections in water, summer party vibes, fun poses", "set_size": 6, "description": "Poolside party content with summer energy"},
    {"id": "cozy_winter", "label": "Cozy Winter", "name": "Winter Cozy Series", "prompt": "cozy winter setting, wearing oversized sweater, fireplace, warm blankets, hot cocoa, soft warm lighting, intimate atmosphere", "set_size": 4, "description": "Warm and cozy winter-themed content"},
    {"id": "boudoir_luxury", "label": "Boudoir Luxury", "name": "Luxury Boudoir Set", "prompt": "luxury boudoir setting, silk sheets, candlelight, wearing lace bodysuit, elegant sensual poses, warm golden tones, professional photography", "set_size": 6, "description": "Premium boudoir photography collection"},
    {"id": "shower_series", "label": "Shower Series", "name": "Shower & Steam Set", "prompt": "glass shower, steam, water droplets on skin, wet hair, warm bathroom lighting, sensual atmosphere, artistic angles", "set_size": 4, "description": "Steamy shower-themed exclusive set"},
    {"id": "silk_and_satin", "label": "Silk & Satin", "name": "Silk & Satin Collection", "prompt": "wearing silk slip dress, satin sheets, luxury bedroom, soft romantic lighting, flowing fabric, sensual elegance, editorial boudoir", "set_size": 4, "description": "Luxurious silk and satin textures"},
    {"id": "artistic_nudes", "label": "Artistic Portraits", "name": "Artistic Portrait Series", "prompt": "fine art portrait, dramatic shadows, sculptural pose, black and white, high contrast, tasteful artistic photography, museum quality", "set_size": 4, "description": "Fine art style portrait collection"},
    {"id": "wet_and_wild", "label": "Wet & Wild", "name": "Wet Look Collection", "prompt": "wet hair slicked back, water on skin, dark moody lighting, rain or shower, glistening skin, editorial wet look photography", "set_size": 4, "description": "Water-themed editorial content"},
]

# ═══════════════════════════════════════════════════════════════════════
# Video Presets
# ═══════════════════════════════════════════════════════════════════════

VIDEO_PRESETS = [
    {"id": "hair_flip", "label": "Hair Flip", "prompt": "Medium close-up. She begins facing the camera with a calm expression, then slowly turns her head and lets her hair sweep across one shoulder. Static camera with a subtle push in, soft natural daylight, sharp focus on her eyes and individual hair strands."},
    {"id": "morning_stretch", "label": "Morning Stretch", "prompt": "Medium shot in bed. She wakes slowly, stretches both arms overhead, arches her back slightly, and exhales with a sleepy smile. Static camera, warm sunrise light through curtains, soft sheets shifting gently, the shot ends with her glancing toward the camera."},
    {"id": "blowing_kiss", "label": "Blowing a Kiss", "prompt": "Close-up portrait. She raises her hand to her lips, gives a playful wink, and slowly blows a kiss toward the camera. Static camera, warm flattering key light, soft background blur, the shot ends on a bright teasing smile."},
    {"id": "coffee_sip", "label": "Coffee Sip", "prompt": "Medium close-up at a table. She lifts a coffee mug, pauses for a small sip, then looks over the rim directly at the camera. Static camera, warm morning window light, visible steam drifting upward, cozy intimate atmosphere."},
    {"id": "looking_over_shoulder", "label": "Looking Over Shoulder", "prompt": "Medium shot from behind. She begins angled away from the camera, then slowly turns her head over one shoulder and holds a mysterious glance. Subtle camera push in, cinematic contrast lighting, the motion stays smooth and deliberate."},
    {"id": "lip_bite", "label": "Lip Bite", "prompt": "Close-up portrait. She holds steady eye contact, gently bites her lower lip, then relaxes into a soft expression without breaking the gaze. Static camera, warm studio key light with soft fill, sharp focus on lips and eyes."},
    {"id": "body_wave", "label": "Body Wave", "prompt": "Medium shot. She begins upright, rolls into one slow body wave, and lets one hand pass through her hair as the motion finishes. Static camera, dark background, moody rim light shaping the body, smooth controlled movement from start to finish."},
    {"id": "robe_drop", "label": "Robe Reveal", "prompt": "Medium close-up. She lightly touches the robe collar, slowly slides it off one shoulder, and settles into a confident pose. Static camera, warm golden bedroom light, visible silk texture catching highlights, the shot ends on direct eye contact."},
    {"id": "mirror_pose", "label": "Mirror Pose", "prompt": "Medium shot beside a mirror. She adjusts her outfit with small natural motions, turns slightly to check her reflection, then relaxes into a composed pose. Static camera, soft indoor light, clean bedroom or dressing-room atmosphere, gentle realistic movement."},
    {"id": "wine_swirl", "label": "Wine Swirl", "prompt": "Medium shot while seated. She slowly swirls a glass of red wine, brings it toward her lips, and takes a measured sip before lowering it again. Static camera, candlelit evening mood, warm highlights on glass and skin, rich intimate atmosphere."},
    {"id": "dance_move", "label": "Dance Move", "prompt": "Medium full-body shot. She lifts her arms, sways into a small rhythmic dance move, and turns slightly with a joyful expression. Static camera, colorful club-inspired lighting, smooth repeatable motion, the shot ends with her facing camera again."},
    {"id": "pool_splash", "label": "Pool Splash", "prompt": "Medium shot at poolside. She steps slowly into the water, creating a gentle splash around her legs, then looks back toward the camera with a relaxed smile. Static camera, bright summer sunlight, wet skin and water reflections rendered in high detail."},
    {"id": "workout_rep", "label": "Workout Rep", "prompt": "Medium full-body shot in a gym. She performs one clean exercise repetition with controlled form, pauses briefly at the top, and resets with focused breathing. Static camera, crisp athletic lighting, visible muscle definition and fabric movement."},
    {"id": "running_slow_mo", "label": "Running Slow-Mo", "prompt": "Medium full-body shot on a beach path. She jogs forward in smooth slow motion as her hair bounces naturally and the wind catches her clothing. Tracking camera moving gently with her, warm sunset light, waves softly moving in the background."},
    {"id": "wind_blown", "label": "Wind Blown", "prompt": "Wide shot. She stands still against the skyline while strong wind pushes her hair and clothing to one side, then she lifts her chin into the light. Static camera, sunset backlight and rim light, powerful posture, cinematic atmosphere."},
    {"id": "rain_walk", "label": "Rain Walk", "prompt": "Medium full-body shot on a city street at night. She walks slowly through light rain, wet hair clinging softly as reflections shimmer across the pavement. Tracking camera with gentle forward motion, neon light in the background, moody cinematic tone."},
    {"id": "candle_blow", "label": "Candle Blow", "prompt": "Medium close-up at a table. She leans toward a cluster of candles, inhales softly, then blows them out in one smooth motion as the flame flickers across her face. Static camera, warm intimate light, the shot ends in a soft afterglow."},
    {"id": "smoke_exhale", "label": "Smoke Exhale", "prompt": "Close-up portrait. She holds still for a beat, then slowly exhales a soft stream of smoke or mist that drifts across the frame. Static camera, dark background, colored edge lighting, mysterious expression, clean controlled motion."},
    {"id": "outfit_reveal", "label": "Outfit Reveal", "prompt": "Medium full-body shot. She turns in a slow confident half spin to reveal the outfit, then settles with both hands on her hips. Static camera, bright studio backdrop, crisp fashion lighting, the shot ends in a clean hero pose."},
    {"id": "wink_and_wave", "label": "Wink & Wave", "prompt": "Close-up portrait. She smiles warmly, gives a small wave, then adds a quick wink before relaxing back into a friendly expression. Static camera, bright natural light, casual social-media intro energy, sharp focus on face and hands."},
    {"id": "tongue_out", "label": "Playful Tongue Out", "prompt": "Medium close-up. She leans slightly toward the camera, flashes a peace sign, sticks her tongue out for a beat, then laughs and relaxes. Static camera, colorful backdrop, bright playful lighting, energetic but simple motion."},
    {"id": "glasses_on", "label": "Glasses On", "prompt": "Medium close-up. She raises a pair of sunglasses, slowly places them on, then lowers her chin into a cool confident look. Static camera, urban background softly out of focus, clean fashion lighting, smooth deliberate timing."},
    {"id": "pillow_hug", "label": "Pillow Hug", "prompt": "Medium shot on a bed. She hugs a pillow close, rolls gently onto one side, and settles into a sleepy smile. Static camera, soft morning light, textured sheets and fabric movement, cozy intimate bedroom mood."},
    {"id": "bedsheet_peek", "label": "Bedsheet Peek", "prompt": "Medium close-up in bed. She starts partly hidden under white sheets, slowly lowers the sheet just below her face, and reveals a playful smile. Static camera, soft window light, tousled hair and gentle fabric movement in clear detail."},
    {"id": "lingerie_walk", "label": "Lingerie Walk", "prompt": "Medium full-body shot. She walks slowly toward the camera with one clean confident stride, then shifts one hand to her hip and holds the pose. Static camera, soft warm studio light, elegant backdrop, poised controlled movement."},
    {"id": "getting_ready", "label": "Getting Ready", "prompt": "Medium shot at a vanity. She applies lipstick with a steady hand, adjusts a strand of hair, and gives herself one final look in the mirror. Static camera, flattering indoor light, behind-the-scenes morning routine with small realistic motions."},
    {"id": "bubble_bath", "label": "Bubble Bath", "prompt": "Medium shot in a bath. She lifts a hand through the foam, lets the bubbles slide away, and settles back into the water with a calm expression. Static camera, warm bathroom light, candle flicker and soft steam, gentle spa-like motion."},
    {"id": "shower_steam", "label": "Shower Steam", "prompt": "Medium close-up through soft steam. Water runs over her shoulders as she slowly tilts her head back and closes her eyes for a moment. Static camera, warm diffused bathroom light, fogged glass and moisture rendered with high detail."},
    {"id": "outfit_change", "label": "Outfit Change", "prompt": "Medium shot designed as a single continuous reveal. She starts adjusting the outer layer of her outfit, opens it in one smooth motion to reveal the styled look underneath, then holds a confident finishing pose. Static camera, clean studio lighting, no jump cuts."},
    {"id": "catwalk", "label": "Catwalk Strut", "prompt": "Medium full-body runway shot. She takes two measured model steps toward the camera with shoulders back and a fierce expression, then pauses at the end mark. Static camera, dramatic editorial lighting, smooth forward motion and clean posture."},
    {"id": "jacket_drop", "label": "Jacket Drop", "prompt": "Medium shot. She slowly slides a jacket off her shoulders, reveals the outfit beneath, and turns her face back toward the camera at the end of the motion. Static camera, moody fashion lighting, crisp fabric detail and confident body language."},
    {"id": "golden_hour", "label": "Golden Hour", "prompt": "Medium shot outdoors at sunset. She shifts her weight slowly, turns slightly into the light, and lets a gentle breeze move her hair while she keeps a serene expression. Static camera, golden backlight, soft lens flare, dreamy high-detail atmosphere."},
    {"id": "neon_glow", "label": "Neon Glow", "prompt": "Medium close-up in an urban night scene. She stands nearly still, slowly lifts her gaze to the camera, and lets the neon colors shift across her face. Static camera, pink and blue edge light, moody cyberpunk atmosphere, sharp skin detail."},
    {"id": "polaroid_snap", "label": "Polaroid Snap", "prompt": "Medium close-up. She lifts a polaroid camera, frames the shot, presses the shutter, and breaks into a candid smile just after the flash. Static camera, vintage room, retro color tone, small natural hand motion and nostalgic mood."},
    {"id": "pillow_fight", "label": "Pillow Fight", "prompt": "Medium shot in a bedroom. She swings a pillow once in a playful arc, laughs as it lands, and settles back into frame with lively energy. Static camera, bright warm indoor light, soft fabric movement, simple readable action."},
    {"id": "ice_cream_lick", "label": "Ice Cream Lick", "prompt": "Medium close-up outdoors. She brings an ice cream cone toward her lips, takes one slow lick, and gives the camera a playful look before smiling. Static camera, summer sunshine, colorful detail in the cone, warm flirty tone."},
    {"id": "flower_smell", "label": "Flower Smell", "prompt": "Medium close-up. She raises a bouquet toward her face, closes her eyes for one slow inhale, and opens them into a soft smile. Static camera, natural garden light, delicate petal texture, romantic calm mood."},
    {"id": "bts_photoshoot", "label": "BTS Photoshoot", "prompt": "Medium shot on a studio set. She relaxes between poses, adjusts her stance, then breaks into a candid laugh as if responding to someone off camera. Static camera, visible studio setup in the background, documentary-style natural motion."},
    {"id": "phone_scroll", "label": "Phone Scroll", "prompt": "Medium shot while lounging on a bed or couch. She scrolls her phone with one hand, shifts her elbows slightly, and glances up from the screen with a relaxed expression. Static camera, soft ambient light, casual candid everyday motion."},
]

# ═══════════════════════════════════════════════════════════════════════
# Persona Presets
# ═══════════════════════════════════════════════════════════════════════

PERSONA_PRESETS = [
    {"id": "girl_next_door", "label": "Girl Next Door", "name": "Ava", "prompt_base": "beautiful young white woman, 23 years old, girl next door look, light brown hair, hazel eyes, natural makeup, warm smile, fit body, freckles, approachable and cute, fair skin"},
    {"id": "glamour_model", "label": "Glamour Model", "name": "Valentina", "prompt_base": "stunning white glamour model, 26 years old, long dark hair, piercing blue eyes, full lips, hourglass figure, flawless porcelain skin, seductive gaze, high cheekbones, sultry, European features"},
    {"id": "alt_egirl", "label": "Alt / E-Girl", "name": "Luna", "prompt_base": "alternative e-girl aesthetic, 22 years old, dyed pastel pink hair, dark eyeliner, pale white skin, petite frame, nose piercing, choker necklace, edgy and playful"},
    {"id": "elegant_mature", "label": "Elegant & Mature", "name": "Sophia", "prompt_base": "elegant mature white woman, 32 years old, auburn hair in waves, brown eyes, sophisticated beauty, slender figure, refined features, confident and classy, minimal jewelry"},
    {"id": "ebony_queen", "label": "Ebony Queen", "name": "Amara", "prompt_base": "gorgeous Black woman, 24 years old, rich dark brown skin, long black curly natural hair, deep brown eyes, full lips, curvaceous body, radiant smile, striking bone structure, glowing complexion"},
    {"id": "dark_goddess", "label": "Dark Goddess", "name": "Zuri", "prompt_base": "stunning dark-skinned Black woman, 27 years old, very dark melanin-rich skin, shaved fade haircut with designs, high cheekbones, fierce expression, tall and statuesque, model proportions, regal bearing"},
    {"id": "caramel_beauty", "label": "Caramel Beauty", "name": "Naomi", "prompt_base": "beautiful light-skinned Black woman, 25 years old, caramel brown skin, honey blonde box braids, hazel-green eyes, full figure, soft features, warm inviting smile, beauty mark on cheek"},
    {"id": "latina_bombshell", "label": "Latina Bombshell", "name": "Isabella", "prompt_base": "gorgeous Latina woman, 25 years old, warm olive tan skin, long dark wavy hair, dark brown eyes, full lips, voluptuous hourglass figure, passionate expression, thick eyebrows, radiant bronze skin"},
    {"id": "latina_petite", "label": "Latina Petite", "name": "Camila", "prompt_base": "beautiful petite Latina woman, 22 years old, light caramel skin, straight dark brown hair with highlights, brown doe eyes, delicate features, slim athletic body, dimples, playful smile"},
    {"id": "japanese_beauty", "label": "Japanese Beauty", "name": "Yuki", "prompt_base": "beautiful Japanese woman, 23 years old, fair porcelain skin, straight black hair with bangs, dark almond-shaped eyes, delicate features, slim elegant body, subtle makeup, graceful and refined"},
    {"id": "korean_idol", "label": "Korean Idol", "name": "Soo-Jin", "prompt_base": "stunning Korean woman, 24 years old, flawless pale skin, long straight dark brown hair, brown eyes with double eyelids, small face, v-shaped jawline, slim petite body, dewy skin, soft pink lips"},
    {"id": "chinese_elegant", "label": "Chinese Elegant", "name": "Mei-Ling", "prompt_base": "elegant Chinese woman, 26 years old, smooth fair skin, long silky black hair, dark expressive eyes, high cheekbones, slender graceful figure, classic beauty, refined sophisticated look, natural elegance"},
    {"id": "thai_exotic", "label": "Thai Exotic", "name": "Kaiya", "prompt_base": "exotic Thai woman, 24 years old, warm golden-brown skin, dark brown wavy hair, dark sparkling eyes, button nose, petite curvy body, bright white smile, tropical beauty, glowing complexion"},
    {"id": "filipina_sweet", "label": "Filipina Sweet", "name": "Maria", "prompt_base": "beautiful Filipina woman, 23 years old, warm tan morena skin, dark wavy hair, dark brown eyes, round face, sweet smile, petite curvy figure, natural beauty, youthful and radiant"},
    {"id": "indian_goddess", "label": "Indian Goddess", "name": "Priya", "prompt_base": "stunning Indian woman, 25 years old, warm brown skin, long thick black hair, large dark expressive eyes, full lips, curvaceous figure, elegant bone structure, kohl-lined eyes, striking classical beauty"},
    {"id": "persian_princess", "label": "Persian Princess", "name": "Yasmin", "prompt_base": "gorgeous Persian woman, 26 years old, olive-toned skin, long dark lustrous hair, large green-hazel eyes, arched eyebrows, full lips, hourglass figure, exotic striking features, natural beauty"},
    {"id": "mixed_blasian", "label": "Mixed — Blasian", "name": "Kira", "prompt_base": "beautiful mixed Black and Asian woman, 24 years old, warm golden-brown skin, curly dark hair, almond-shaped brown eyes, full lips, toned athletic body, unique striking features, exotic blend"},
    {"id": "mixed_lightskin", "label": "Mixed — Light Skin", "name": "Aaliyah", "prompt_base": "gorgeous mixed-race woman, 23 years old, light brown skin, loose curly brown hair with blonde highlights, green-hazel eyes, freckles on nose, slim thick body, ethnically ambiguous beauty, radiant"},
    {"id": "fitness_influencer", "label": "Fitness Influencer", "name": "Jordan", "prompt_base": "athletic fitness model woman, 25 years old, toned muscular body, blonde ponytail, green eyes, sun-kissed tan skin, confident expression, strong jawline, healthy glow, six-pack abs visible"},
    {"id": "fiery_redhead", "label": "Fiery Redhead", "name": "Scarlett", "prompt_base": "stunning redhead woman, 24 years old, pale freckled skin, long wavy bright red hair, vivid green eyes, full lips, slim curvy body, fiery expression, scattered freckles across shoulders and chest"},
]

# ═══════════════════════════════════════════════════════════════════════
# Negative Prompt Presets
# ═══════════════════════════════════════════════════════════════════════

_NEG_DEFAULT = "deformed, distorted, disfigured, poorly drawn, bad anatomy, wrong anatomy, extra limb, missing limb, floating limbs, mutated hands, extra fingers, fused fingers, too many fingers, long neck, malformed, ugly, blurry, watermark, text, signature, logo"
_NEG_QUALITY = "low quality, low resolution, out of focus, grainy, noisy, overexposed, underexposed, washed out, pixelated, jpeg artifacts, compression artifacts"
_NEG_FACE = "deformed face, asymmetric face, cross-eyed, ugly face, duplicate face, poorly drawn face, cloned face, disfigured face, bad teeth, crooked teeth"
_NEG_BODY = "extra arms, extra legs, extra hands, missing fingers, fused body parts, conjoined, bad proportions, gross proportions, disproportionate, duplicate body parts"
_NEG_FULL = f"{_NEG_DEFAULT}, {_NEG_QUALITY}, {_NEG_FACE}, {_NEG_BODY}"

NEGATIVE_PROMPT_PRESETS = [
    {"id": "default", "label": "\u26d4 Default", "prompt": _NEG_DEFAULT, "description": "Blocks common anatomy and quality issues"},
    {"id": "quality", "label": "\U0001f4f7 Quality", "prompt": _NEG_QUALITY, "description": "Blocks low-resolution and compression artifacts"},
    {"id": "face", "label": "\U0001f464 Face Fix", "prompt": _NEG_FACE, "description": "Blocks face deformities and asymmetry"},
    {"id": "body", "label": "\U0001f9b4 Body Fix", "prompt": _NEG_BODY, "description": "Blocks extra/missing limbs and bad proportions"},
    {"id": "full", "label": "\U0001f6e1\ufe0f Full Protection", "prompt": _NEG_FULL, "description": "Maximum protection \u2014 all categories combined"},
]

# ═══════════════════════════════════════════════════════════════════════
# LoRA Discovery
# ═══════════════════════════════════════════════════════════════════════

LORA_DIR = Path.home() / "Documents" / "ComfyUI" / "models" / "loras"

RECOMMENDED_LORAS = [
    {"id": "illustration_qwen", "name": "Illustration (Qwen)", "filename": "illustration-1.0-qwen-image.safetensors", "description": "Illustration / anime style for Flux", "category": "Style"},
    {"id": "flux_realism", "name": "Flux Realism LoRA", "filename": "flux_realism_lora.safetensors", "description": "Enhanced photorealism for Flux generations", "category": "Realism"},
    {"id": "detail_tweaker", "name": "Detail Tweaker XL", "filename": "detail_tweaker_xl.safetensors", "description": "Adds fine detail to skin, fabric, and textures", "category": "Detail"},
    {"id": "skin_texture", "name": "Skin Texture", "filename": "skin_texture_flux.safetensors", "description": "Realistic skin pores, subtle imperfections", "category": "Realism"},
    {"id": "eye_detail", "name": "Eye Detail / Catchlight", "filename": "eye_detail_flux.safetensors", "description": "Sharper eyes with natural catchlights", "category": "Detail"},
    {"id": "film_grain", "name": "Film Grain / Analog", "filename": "film_grain_flux.safetensors", "description": "Cinematic analog film look with grain", "category": "Style"},
    {"id": "bokeh_depth", "name": "Bokeh / Depth of Field", "filename": "bokeh_dof_flux.safetensors", "description": "Professional background blur and bokeh", "category": "Photography"},
    {"id": "soft_lighting", "name": "Soft Lighting", "filename": "soft_lighting_flux.safetensors", "description": "Flattering soft studio / golden hour lighting", "category": "Lighting"},
    {"id": "nsfw_body", "name": "Realistic Body", "filename": "realistic_body_flux.safetensors", "description": "Improved body proportions and anatomy", "category": "Anatomy"},
    {"id": "fashion_photo", "name": "Fashion Photography", "filename": "fashion_photography_flux.safetensors", "description": "High-fashion editorial photography look", "category": "Photography"},
]


# ── Endpoints ────────────────────────────────────────────────────────

@router.get("/presets/scenes")
def get_scene_presets():
    return SCENE_PRESETS


@router.get("/presets/personas")
def get_persona_presets():
    return PERSONA_PRESETS


@router.get("/presets/content-sets")
def get_content_set_presets():
    return CONTENT_SET_PRESETS


@router.get("/presets/videos")
def get_video_presets():
    return VIDEO_PRESETS


@router.get("/presets/negative-prompts")
def get_negative_prompt_presets():
    return NEGATIVE_PROMPT_PRESETS


@router.get("/loras")
def list_loras():
    installed = []
    if LORA_DIR.exists():
        for f in sorted(LORA_DIR.glob("*.safetensors")):
            installed.append({"filename": f.name, "name": f.stem.replace("-", " ").replace("_", " ").title(), "size_mb": round(f.stat().st_size / (1024 * 1024), 1)})

    installed_names = {l["filename"] for l in installed}
    recommended = []
    for rec in RECOMMENDED_LORAS:
        recommended.append({**rec, "installed": rec["filename"] in installed_names})

    return {"installed": installed, "recommended": recommended}


@router.get("/image-model-profiles")
def list_image_model_profiles():
    try:
        from .. import comfy_api
    except ImportError:
        import comfy_api

    profiles = []
    for key, value in comfy_api.IMAGE_MODEL_PROFILES.items():
        profiles.append(
            {
                "id": key,
                "unet_name": value.get("unet_name"),
                "vae_name": value.get("vae_name"),
                "default_steps": value.get("steps"),
                "default_guidance": value.get("guidance"),
            }
        )

    return {"profiles": sorted(profiles, key=lambda p: p["id"])}
