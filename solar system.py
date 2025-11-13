import pygame
import random
import math
import colorsys

# --- Initialization ---
pygame.init()
WIDTH, HEIGHT = 1400, 900
screen = pygame.display.set_mode((WIDTH, HEIGHT))
pygame.display.set_caption("🌌 The Cosmic Sandbox 🌌")
clock = pygame.time.Clock()
font = pygame.font.SysFont("Arial", 16)

# --- Constants & Helpers ---
G_CONSTANT = 1.2
SUPERNOVA_MASS_LIMIT = 25
PULSAR_MASS_LIMIT = 40
PARTICLE_LIFETIME = 100
MAX_BODIES = 300  # Performance cap
PLANET_INTERACTIONS_ENABLED = True

def hsv_to_rgb(h, s, v):
    """Convert HSV color to RGB color."""
    rgb = colorsys.hsv_to_rgb(h, s, v)
    return tuple(int(c * 255) for c in rgb)

def get_color_for_mass(mass):
    """Returns a color based on a star's mass, from red dwarf to blue giant."""
    if mass < 4:
        return (255, 180, 120)  # Reddish for small stars
    elif mass < 10:
        return (255, 255, 220)  # Yellow/White for medium stars
    elif mass < SUPERNOVA_MASS_LIMIT:
        return (170, 220, 255)  # Bright Blue for massive stars
    else:
        return (210, 240, 255)  # Intense blue-white for pre-supernova stars

class UIManager:
    """Handles drawing all UI text elements."""
    def __init__(self, font):
        self.font = font
        self.paused = False

    def draw(self, surface, body_count, particle_count, gravity, tool):
        draw_text = self.draw_text  # Local alias for speed
        draw_text("[L/R Mouse] Attract/Repel", 10, 10)
        draw_text("[S] Star | [B] Black Hole | [N] Pulsar | [Q] Quasar", 10, 30)
        draw_text("[G] Galaxy | [O] Solar System | [P] Planet Interactions", 10, 50)
        draw_text("[SPACE] Pause | [R] Reset to Solar System | [+/-] Gravity", 10, 70)
        draw_text(f"Objects: {body_count} | Particles: {particle_count}", 10, 90)
        draw_text(f"Gravity: {gravity:.3f} | Tool: {tool}", 10, 110)
        pi_status = "On" if PLANET_INTERACTIONS_ENABLED else "Off"
        draw_text(f"Planet Interactions: {pi_status}", 10, 130)
        
        if self.paused:
            paused_text = self.font.render("PAUSED", True, (255, 255, 255))
            surface.blit(paused_text, (WIDTH // 2 - paused_text.get_width() // 2, HEIGHT // 2))

    def draw_text(self, text, x, y, color=(255, 255, 255)):
        text_surface = self.font.render(text, True, color)
        screen.blit(text_surface, (x, y))

# --- Effect Classes ---
class SupernovaFlash:
    """A visual effect for a supernova explosion."""
    def __init__(self, x, y, max_radius=300, duration=40):
        self.x, self.y = x, y
        self.max_radius = max_radius
        self.duration = self.lifetime = duration
        self.alive = True

    def update(self):
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False

    def draw(self, surface):
        progress = (self.duration - self.lifetime) / self.duration
        current_radius = int(progress * self.max_radius)
        alpha = int(255 * (1 - progress**2))
        
        s = pygame.Surface((current_radius * 2, current_radius * 2), pygame.SRCALPHA)
        color = (255, 255, 230, alpha)
        pygame.draw.circle(s, color, (current_radius, current_radius), current_radius)
        surface.blit(s, (self.x - current_radius, self.y - current_radius), special_flags=pygame.BLEND_RGBA_ADD)

# --- Celestial Body Classes ---
class Particle:
    """Represents a short-lived particle, for explosions and effects."""
    def __init__(self, x, y, vx, vy, color, lifetime, gravity_affected=False):
        self.x, self.y = x, y
        self.vx, self.vy = vx, vy
        self.color = color
        self.lifetime = self.initial_lifetime = lifetime
        self.gravity_affected = gravity_affected
        self.alive = True

    def update(self, bodies=[]):
        """Update particle position and lifetime."""
        if self.gravity_affected:
            ax = ay = 0
            for body in bodies:
                if isinstance(body, BlackHole): # Only black holes and quasars affect particles
                    dx, dy = body.x - self.x, body.y - self.y
                    dist_sq = dx*dx + dy*dy + 100 # Add damping
                    force = G_CONSTANT * body.mass / dist_sq
                    dist = math.sqrt(dist_sq)
                    ax += force * dx / dist
                    ay += force * dy / dist
            self.vx += ax
            self.vy += ay

        self.x += self.vx
        self.y += self.vy
        self.lifetime -= 1
        if self.lifetime <= 0:
            self.alive = False

    def draw(self, surface):
        """Draw the particle, fading it out over its lifetime."""
        if self.lifetime > 0:
            alpha = int(255 * (self.lifetime / self.initial_lifetime))
            radius = 1 if self.gravity_affected else 2
            s = pygame.Surface((radius * 2, radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*self.color, alpha), (radius, radius), radius)
            surface.blit(s, (self.x - radius, self.y - radius), special_flags=pygame.BLEND_RGBA_ADD)

class CelestialBody:
    """Base class for all objects in the simulation."""
    def __init__(self, x, y, mass, color, vx=0, vy=0, name=""):
        self.x, self.y = x, y
        self.mass = mass
        self.radius = int(math.sqrt(abs(self.mass)) * 2.5) if mass > 0 else 1
        self.color = color
        self.vx, self.vy = vx, vy
        self.name = name
        self.static = False

    def update_velocity(self, others):
        """Update velocity based on gravitational pull from other bodies."""
        ax = ay = 0
        for other in others:
            if other is self: continue

            # For solar system stability, disable planet-planet gravity.
            if not PLANET_INTERACTIONS_ENABLED:
                if isinstance(self, Planet) and isinstance(other, Planet):
                    continue # Skip gravity calculation between planets.

            dx, dy = other.x - self.x, other.y - self.y
            dist_sq = dx*dx + dy*dy
            if dist_sq < 25: dist_sq = 25 # Prevent extreme forces
            force = G_CONSTANT * other.mass / dist_sq
            dist = math.sqrt(dist_sq)
            ax += force * dx / dist
            ay += force * dy / dist
        self.vx += ax
        self.vy += ay

    def update_position(self):
        """Update position based on current velocity."""
        self.x += self.vx
        self.y += self.vy
        # self.x %= WIDTH  # Removed screen wrapping for more realistic orbits
        # self.y %= HEIGHT # Removed screen wrapping for more realistic orbits
    
    def draw_glow(self, surface, glow_color, intensity=0.1, steps=10):
        """Draw a soft glow effect around the body."""
        for i in range(steps, 0, -1):
            alpha = int(255 * intensity * (i / steps)**2)
            glow_radius = self.radius + i * 2
            s = pygame.Surface((glow_radius * 2, glow_radius * 2), pygame.SRCALPHA)
            pygame.draw.circle(s, (*glow_color, alpha), (glow_radius, glow_radius), glow_radius)
            surface.blit(s, (self.x - glow_radius, self.y - glow_radius), special_flags=pygame.BLEND_RGBA_ADD)

    def draw(self, surface):
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        if self.name:
            text_surf = font.render(self.name, True, (200, 200, 200))
            surface.blit(text_surf, (self.x + self.radius + 5, self.y))


class Planet(CelestialBody):
    """A simple body that represents a planet, with an orbit trail."""
    def __init__(self, x, y, mass, color, vx=0, vy=0, name=""):
        super().__init__(x, y, mass, color, vx, vy, name)
        self.orbit = []

    def update_position(self):
        super().update_position()
        self.orbit.append((self.x, self.y))
        if len(self.orbit) > 500: self.orbit.pop(0)
    
    def draw(self, surface):
        if len(self.orbit) > 2:
            try: pygame.draw.aalines(surface, self.color, False, self.orbit, 1)
            except: pygame.draw.lines(surface, self.color, False, self.orbit, 1)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)
        if self.name:
            text_surf = font.render(self.name, True, (200, 200, 200))
            surface.blit(text_surf, (self.x + self.radius + 2, self.y))

class Star(CelestialBody):
    """Represents a star with a glowing trail."""
    def __init__(self, x, y, mass, vx=0, vy=0):
        super().__init__(x, y, mass, get_color_for_mass(mass), vx, vy)
        self.orbit = []
        self.radius = int(math.sqrt(self.mass) * 3)

    def update_position(self):
        super().update_position()
        self.orbit.append((self.x, self.y))
        if len(self.orbit) > 100: self.orbit.pop(0)

    def draw(self, surface):
        self.draw_glow(surface, self.color, intensity=0.15)
        if len(self.orbit) > 2:
            try: pygame.draw.aalines(surface, self.color, False, self.orbit, 1)
            except: pygame.draw.lines(surface, self.color, False, self.orbit, 1)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

class BlackHole(CelestialBody):
    """Represents a black hole that consumes other bodies and warps space."""
    def __init__(self, x, y, mass=500, vx=0, vy=0):
        super().__init__(x, y, mass, (0, 0, 0), vx, vy)
        self.accretion_disk_hue = random.random()
        self.radius = int(math.sqrt(self.mass) * 1.5)
    
    def draw_accretion_disk(self, surface):
        self.accretion_disk_hue = (self.accretion_disk_hue + 0.01) % 1.0
        disk_color = hsv_to_rgb(self.accretion_disk_hue, 0.8, 1)
        pygame.draw.circle(surface, disk_color, (int(self.x), int(self.y)), self.radius + 10, 2)
        pygame.draw.circle(surface, disk_color, (int(self.x), int(self.y)), self.radius + 15, 1)

    def draw(self, surface):
        self.draw_glow(surface, (50, 50, 100), intensity=0.3, steps=15)
        self.draw_accretion_disk(surface)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

    def draw_lensing_effect(self, surface):
        """ A simplified gravitational lensing effect. """
        lens_radius = self.radius * 6
        if lens_radius <= 0: return
        
        # Create a surface to draw the distorted view on
        lens_surface = pygame.Surface((lens_radius * 2, lens_radius * 2), pygame.SRCALPHA)
        
        # Grab the part of the screen behind the black hole
        grab_rect = pygame.Rect(self.x - lens_radius, self.y - lens_radius, lens_radius * 2, lens_radius * 2)
        
        try:
            sub_surface = surface.subsurface(grab_rect)
            # Create a copy that we can manipulate
            lens_content = pygame.transform.scale(sub_surface, (lens_radius * 2, lens_radius * 2))
        except ValueError: # Happens if black hole is at the screen edge
            return

        px_array = pygame.PixelArray(lens_content)

        for i in range(lens_radius * 2):
            for j in range(lens_radius * 2):
                dx = i - lens_radius
                dy = j - lens_radius
                dist_from_center = math.hypot(dx, dy)

                if dist_from_center == 0 or dist_from_center > lens_radius:
                    continue

                # The core of the lensing effect: displace pixels based on mass and distance
                strength = (self.mass / 2000) * (1 - dist_from_center / lens_radius)
                
                # Calculate new coordinates for the pixel lookup
                new_x = int(lens_radius + dx * (1 - strength))
                new_y = int(lens_radius + dy * (1 - strength))

                if 0 <= new_x < lens_radius * 2 and 0 <= new_y < lens_radius * 2:
                    px_array[i, j] = px_array[new_x, new_y]
        
        del px_array # Unlock the surface
        lens_surface.blit(lens_content, (0, 0))
        surface.blit(lens_surface, grab_rect.topleft)

    def consume(self, bodies):
        consumed = []
        for body in bodies:
            if body is self or isinstance(body, BlackHole): continue
            dx, dy = body.x - self.x, body.y - self.y
            if math.hypot(dx, dy) < self.radius:
                consumed.append(body)
                self.mass += body.mass * 0.25 # Grow more substantially
                self.radius = int(math.sqrt(self.mass) * 1.5)
        return consumed

class Quasar(BlackHole):
    """ A supermassive black hole with powerful jets. """
    def __init__(self, x, y, mass=2000, vx=0, vy=0):
        super().__init__(x, y, mass, vx, vy)
        self.angle = random.uniform(0, 2 * math.pi)
        self.rotation_speed = 0.03
        self.radius = int(math.sqrt(self.mass) * 1.2)
    
    def update(self, particles_list):
        self.angle = (self.angle + self.rotation_speed) % (2 * math.pi)
        if random.random() < 0.9: # Emit particles frequently
            jet_speed = 15
            p_vx = math.cos(self.angle) * jet_speed
            p_vy = math.sin(self.angle) * jet_speed
            color = hsv_to_rgb((self.accretion_disk_hue + 0.5) % 1.0, 0.9, 1)
            
            particles_list.append(Particle(self.x, self.y, p_vx, p_vy, color, 120, gravity_affected=True))
            particles_list.append(Particle(self.x, self.y, -p_vx, -p_vy, color, 120, gravity_affected=True))

    def draw_accretion_disk(self, surface):
        self.accretion_disk_hue = (self.accretion_disk_hue + 0.02) % 1.0
        for i in range(5):
             hue = (self.accretion_disk_hue + i*0.05) % 1.0
             color = hsv_to_rgb(hue, 0.9, 1)
             pygame.draw.circle(surface, color, (int(self.x), int(self.y)), self.radius + 10 + i * 5, 2)


class Pulsar(CelestialBody):
    """A rapidly spinning neutron star that emits particle jets."""
    def __init__(self, x, y, mass, vx=0, vy=0):
        super().__init__(x, y, mass, (220, 255, 255), vx, vy)
        self.radius = int(math.sqrt(mass) * 1.2) # Very dense
        self.angle = random.uniform(0, 2 * math.pi)
        self.rotation_speed = 0.1

    def update(self, particles_list):
        self.angle = (self.angle + self.rotation_speed) % (2 * math.pi)
        if random.random() < 0.8: # Don't emit every frame
            jet_speed = 8
            p_vx = math.cos(self.angle) * jet_speed
            p_vy = math.sin(self.angle) * jet_speed
            particles_list.append(Particle(self.x, self.y, p_vx, p_vy, self.color, 60))
            particles_list.append(Particle(self.x, self.y, -p_vx, -p_vy, self.color, 60))

    def draw(self, surface):
        self.draw_glow(surface, self.color, intensity=0.4, steps=8)
        pygame.draw.circle(surface, self.color, (int(self.x), int(self.y)), self.radius)

# --- Game Setup & Generation Functions ---
def create_background_stars(num):
    """Creates a list of stars for the background starfield."""
    return [(random.randint(0, WIDTH), random.randint(0, HEIGHT), random.uniform(0.5, 1.5)) for _ in range(num)]

def draw_background_stars(surface, stars):
    """Draws the twinkling background stars."""
    for x, y, brightness in stars:
        flicker = random.randint(int(brightness * 60), int(brightness * 120))
        color = (flicker, flicker, flicker)
        surface.set_at((x, y), color)

def create_galaxy(center_x, center_y, num_systems=3, spawn_radius=250):
    """Creates multiple small solar systems in a given area."""
    global PLANET_INTERACTIONS_ENABLED
    PLANET_INTERACTIONS_ENABLED = True
    bodies = []
    
    for _ in range(num_systems):
        # Determine a center for this new solar system within the spawn radius
        system_cx = center_x + random.uniform(-spawn_radius, spawn_radius)
        system_cy = center_y + random.uniform(-spawn_radius, spawn_radius)

        # Create the central star for this system
        star_mass = random.uniform(800, 2000)
        # Give the whole system a slight drift velocity
        star_vx = random.uniform(-0.5, 0.5)
        star_vy = random.uniform(-0.5, 0.5)
        
        star = Star(system_cx, system_cy, star_mass, vx=star_vx, vy=star_vy)
        bodies.append(star)
        
        # Create a few planets orbiting the star
        num_planets = random.randint(2, 5)
        for i in range(num_planets):
            dist = random.uniform(40, 150)
            angle = random.uniform(0, 2 * math.pi)
            
            px = system_cx + math.cos(angle) * dist
            py = system_cy + math.sin(angle) * dist
            
            # Calculate orbital velocity
            try:
                orbital_v = math.sqrt((G_CONSTANT * star_mass) / dist)
            except ValueError:
                orbital_v = 0 # Avoid math domain error if dist is 0
            
            # Velocity should be perpendicular to the radius vector
            orbital_vx = -math.sin(angle) * orbital_v
            orbital_vy = math.cos(angle) * orbital_v

            # The planet's final velocity is its orbit + the system's drift
            final_vx = star_vx + orbital_vx
            final_vy = star_vy + orbital_vy

            planet_mass = random.uniform(0.1, 2.5)
            planet_color = (random.randint(100, 255), random.randint(100, 255), random.randint(100, 255))
            
            bodies.append(Planet(px, py, planet_mass, planet_color, final_vx, final_vy))
            
    return bodies

def create_solar_system():
    """Creates a simplified model of our solar system."""
    global PLANET_INTERACTIONS_ENABLED
    PLANET_INTERACTIONS_ENABLED = False # Disable for stable orbits by default
    bodies = []
    cx, cy = WIDTH // 2, HEIGHT // 2
    
    # Sun
    sun_mass = 20000
    bodies.append(Star(cx, cy, 30))
    bodies[-1].mass = sun_mass # Override mass for physics but keep star appearance
    bodies[-1].name = "Sun"
    bodies[-1].static = True # Make the sun stationary

    # Planet data: [name, mass, color, distance_from_sun]
    planet_data = [
        ("Mercury", 0.1, (150, 150, 150), 60),
        ("Venus", 0.8, (200, 150, 100), 90),
        ("Earth", 1.0, (100, 150, 255), 130),
        ("Mars", 0.2, (255, 100, 50), 180),
        ("Jupiter", 300, (210, 180, 140), 280),
        ("Saturn", 95, (220, 210, 180), 380),
        ("Uranus", 14, (180, 220, 220), 460),
        ("Neptune", 17, (100, 100, 255), 520)
    ]
    
    for name, mass, color, dist in planet_data:
        angle = random.uniform(0, 2 * math.pi)
        px = cx + math.cos(angle) * dist
        py = cy + math.sin(angle) * dist
        
        # Calculate orbital velocity for a circular orbit
        orbital_v = math.sqrt((G_CONSTANT * sun_mass) / dist)
        
        # Velocity should be perpendicular to the radius vector
        vx = -math.sin(angle) * orbital_v
        vy = math.cos(angle) * orbital_v
        
        bodies.append(Planet(px, py, mass, color, vx, vy, name))

    return bodies

celestial_bodies = create_solar_system()
particles = []
effects = [] # For things like supernova flashes
background_stars = create_background_stars(800)
background_hue = random.random()
ui_manager = UIManager(font)
current_tool = "None"

# --- Main Game Loop ---
running = True
while running:
    for event in pygame.event.get():
        if event.type == pygame.QUIT: running = False
        if event.type == pygame.KEYDOWN:
            if event.key == pygame.K_SPACE: ui_manager.paused = not ui_manager.paused
            if event.key == pygame.K_p: PLANET_INTERACTIONS_ENABLED = not PLANET_INTERACTIONS_ENABLED
            if event.key == pygame.K_r:
                celestial_bodies = create_solar_system()
                particles.clear()
                effects.clear()
                G_CONSTANT = 1.2
            if event.key == pygame.K_o:
                celestial_bodies = create_solar_system()
                particles.clear()
                effects.clear()
            if event.key == pygame.K_EQUALS or event.key == pygame.K_PLUS: G_CONSTANT *= 1.2
            if event.key == pygame.K_MINUS: G_CONSTANT /= 1.2
            if len(celestial_bodies) < MAX_BODIES:
                mx, my = pygame.mouse.get_pos()
                if event.key == pygame.K_s: celestial_bodies.append(Star(mx, my, random.uniform(2, 6)))
                if event.key == pygame.K_b: celestial_bodies.append(BlackHole(mx, my))
                if event.key == pygame.K_n: celestial_bodies.append(Pulsar(mx, my, 15))
                if event.key == pygame.K_q: celestial_bodies.append(Quasar(mx, my))
                if event.key == pygame.K_g: celestial_bodies.extend(create_galaxy(mx, my))


    # --- Background ---
    background_hue = (background_hue + 0.0001) % 1.0
    bg_color = hsv_to_rgb(background_hue, 0.8, 0.05)
    screen.fill(bg_color)
    draw_background_stars(screen, background_stars)

    # --- Simulation Logic ---
    if not ui_manager.paused:
        # User interaction: Gravity Wells
        mouse_buttons = pygame.mouse.get_pressed()
        mx, my = pygame.mouse.get_pos()
        interaction_bodies = list(celestial_bodies) # Create a copy for this frame
        current_tool = "None"
        if mouse_buttons[0]: # Left mouse: Attract
            interaction_bodies.append(CelestialBody(mx, my, 800, (0,0,0)))
            current_tool = "Attract"
        if mouse_buttons[2]: # Right mouse: Repel
            interaction_bodies.append(CelestialBody(mx, my, -800, (0,0,0)))
            current_tool = "Repel"
        
        bodies_to_remove = set()
        bodies_to_add = []

        # Consume bodies
        for body in interaction_bodies:
            if isinstance(body, BlackHole):
                bodies_to_remove.update(body.consume(interaction_bodies))

        # Merge, Supernova, Pulsar creation
        for i, body1 in enumerate(celestial_bodies):
            if body1 in bodies_to_remove: continue
            for j, body2 in enumerate(celestial_bodies[i+1:], i+1):
                if body2 in bodies_to_remove: continue
                if isinstance(body1, Star) and isinstance(body2, Star):
                    dx, dy = body1.x - body2.x, body1.y - body2.y
                    if math.hypot(dx, dy) < body1.radius + body2.radius:
                        total_mass = body1.mass + body2.mass
                        new_x = (body1.x*body1.mass + body2.x*body2.mass) / total_mass
                        new_y = (body1.y*body1.mass + body2.y*body2.mass) / total_mass
                        bodies_to_remove.add(body1)
                        bodies_to_remove.add(body2)

                        if total_mass > SUPERNOVA_MASS_LIMIT:
                            effects.append(SupernovaFlash(new_x, new_y))
                            for _ in range(300):
                                angle = random.uniform(0, 2 * math.pi)
                                speed = random.uniform(1, 7)
                                p_color = random.choice([(255, 255, 220), body1.color, body2.color])
                                particles.append(Particle(new_x, new_y, math.cos(angle)*speed, math.sin(angle)*speed, p_color, PARTICLE_LIFETIME, gravity_affected=True))
                            
                            # Shockwave
                            for body in interaction_bodies:
                                if body not in bodies_to_remove:
                                    dx, dy = body.x - new_x, body.y - new_y
                                    dist_sq = dx*dx + dy*dy + 1
                                    if dist_sq > 0:
                                        force = 800 / dist_sq
                                        body.vx += force * (dx / math.sqrt(dist_sq))
                                        body.vy += force * (dy / math.sqrt(dist_sq))
                            # Remnant
                            if total_mass > PULSAR_MASS_LIMIT:
                                bodies_to_add.append(BlackHole(new_x, new_y, total_mass))
                            else:
                                bodies_to_add.append(Pulsar(new_x, new_y, total_mass, vx=0, vy=0))
                        else: # Regular merge
                            new_vx = (body1.vx * body1.mass + body2.vx * body2.mass) / total_mass
                            new_vy = (body1.vy * body1.mass + body2.vy * body2.mass) / total_mass
                            bodies_to_add.append(Star(new_x, new_y, total_mass, new_vx, new_vy))

        celestial_bodies = [b for b in celestial_bodies if b not in bodies_to_remove]
        celestial_bodies.extend(bodies_to_add)
        
        if len(celestial_bodies) > MAX_BODIES:
            celestial_bodies.sort(key=lambda b: b.mass)
            celestial_bodies = celestial_bodies[-MAX_BODIES:]
            
        # Update bodies and particles
        for body in celestial_bodies:
            if not body.static:
                body.update_velocity(interaction_bodies)
                body.update_position()
            if isinstance(body, (Pulsar, Quasar)):
                body.update(particles)
        
        for p in particles: p.update(interaction_bodies)
        for e in effects: e.update()
        particles = [p for p in particles if p.alive]
        effects = [e for e in effects if e.alive]


    # --- Drawing ---
    # Draw all non-black hole objects first
    for body in celestial_bodies:
        if not isinstance(body, BlackHole):
            body.draw(screen)

    # Apply lensing effects and draw black holes last so they appear on top
    black_holes = [b for b in celestial_bodies if isinstance(b, BlackHole)]
    for bh in black_holes:
        bh.draw_lensing_effect(screen)
    for bh in black_holes:
        bh.draw(screen) # Draw the black hole itself over the lensed area

    for p in particles: p.draw(screen)
    for e in effects: e.draw(screen)
    ui_manager.draw(screen, len(celestial_bodies), len(particles), G_CONSTANT, current_tool)

    pygame.display.flip()
    clock.tick(60)
pygame.quit()




