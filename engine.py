import tcod as libtcod
from components.fighter import Fighter
from components.inventory import Inventory
from game_states import GameStates
from game_messages import Message, MessageLog
from input_handlers import handle_keys
from map_objects.game_map import GameMap
from entity import Entity, get_blocking_entities_at_location
from render_functions import clear_all, render_all, RenderOrder
from death_functions import kill_monster, kill_player
from fov_functions import initialize_fov, recompute_fov


def main():
	# These control our console size
	screen_width = 80
	screen_height = 50

	#These control our UI console
	bar_width = 20
	panel_height = 7
	panel_y = screen_height - panel_height
	message_x = bar_width + 2
	message_width = screen_width - bar_width - 2
	message_height = panel_height - 1

	# These control our map and room params
	map_width = 80
	map_height = 43
	room_max_size = 10
	room_min_size = 6
	max_rooms = 30

	# These control our field of view
	fov_algorithm = 0
	fov_light_walls = True
	fov_radius = 10

	#for our entities
	max_monsters_per_room = 3
	max_items_per_room = 2

	colors = {
		'dark_wall': libtcod.Color(0, 0, 100),
		'dark_ground': libtcod.Color(50, 50, 150),
		#'light_wall': libtcod.Color(130, 110, 50),
		'light_wall': libtcod.Color(0, 0, 100),
		'light_ground': libtcod.Color(200, 180, 50)
	}

	#initialize player and add him to entities list
	fighter_compenent = Fighter(hp=30, defense=2, power=5)
	inventory_component = Inventory(26)
	player = Entity(0, 0, '@', libtcod.white, 'Player', blocks=True, render_order=RenderOrder.ACTOR, 
					fighter=fighter_compenent, inventory=inventory_component)
	entities = [player]

	#set the art to be used
	libtcod.console_set_custom_font('arial10x10.png', libtcod.FONT_TYPE_GREYSCALE | libtcod.FONT_LAYOUT_TCOD)
	#title displayed on console
	libtcod.console_init_root(screen_width, screen_height, 'libtcod tutorial revised', False)
	
	#create a new console variables
	con = libtcod.console_new(screen_width, screen_height)
	panel = libtcod.console_new(screen_width, panel_height)

	# initialize a new map object
	game_map = GameMap(map_width, map_height)
	# build new map based on everything we've created.
	game_map.make_map(max_rooms, room_min_size, room_max_size, map_width, map_height, player, entities, 
					max_monsters_per_room, max_items_per_room)
	
	# bool to store whether we update fov or not
	fov_recompute = True
	fov_map = initialize_fov(game_map)

	message_log = MessageLog(message_x, message_width, message_height)

	# key and mouse to capture input
	key = libtcod.Key()
	mouse = libtcod.Mouse()
	mouse_pos = 0
	game_state = GameStates.PLAYERS_TURN
	previous_game_state = game_state

	#game loop that keeps things going
	while not libtcod.console_is_window_closed():
		libtcod.sys_check_for_event(libtcod.EVENT_KEY_PRESS | libtcod.EVENT_MOUSE, key, mouse)

		# This is will update the mouse when it is moved.
		if mouse.x != mouse_pos:
			fov_recompute = True
			mouse_pos = mouse.x

		#if player doesn't move fov won't update.
		if fov_recompute:
			recompute_fov(fov_map, player.x, player.y, fov_radius, fov_light_walls, fov_algorithm)

		#update everything
		render_all(con, panel, entities, player, game_map, fov_map, fov_recompute, message_log, screen_width, screen_height,
					bar_width, panel_height, panel_y, mouse, colors, game_state)
		fov_recompute = False

		libtcod.console_flush()

		clear_all(con, entities)

		action = handle_keys(key, game_state)

		#----ACTIONS-----
		move = action.get('move')
		pickup = action.get('pickup')
		show_inventory = action.get('show_inventory')
		inventory_index = action.get('inventory_index')
		drop_inventory = action.get('drop_inventory')
		exit = action.get('exit')
		fullscreen = action.get('fullscreen')

		player_turn_results = []

		if move and game_state == GameStates.PLAYERS_TURN:
			dx, dy = move
			fov_recompute = True

			destination_x = player.x + dx
			destination_y = player.y + dy

			if not game_map.is_blocked(destination_x, destination_y):
				target = get_blocking_entities_at_location(entities, destination_x, destination_y)

				if target:
					attack_results = player.fighter.attack(target)
					player_turn_results.extend(attack_results)
				else:
					player.move(dx, dy)
					fov_recompute = True
				#after player's turn set to enemy turn
				game_state = GameStates.ENEMY_TURN
		elif pickup and game_state == GameStates.PLAYERS_TURN:
			fov_recompute = True
			for entity in entities:
				if entity.item and entity.x == player.x and entity.y == player.y:
					pickup_results = player.inventory.add_item(entity)
					player_turn_results.extend(pickup_results)

					break
			else:
				message_log.add_message(Message('There is nothing here to pick up.', libtcod.yellow))

		if show_inventory:
			fov_recompute = True
			previous_game_state = game_state
			game_state = GameStates.SHOW_INVENTORY
		
		if drop_inventory:
			fov_recompute = True
			previous_game_state = game_state
			game_state = GameStates.DROP_INVENTORY
		
		if inventory_index is not None and previous_game_state != GameStates.PLAYER_DEAD and inventory_index < len(
				player.inventory.items):
			fov_recompute = True
			item = player.inventory.items[inventory_index]
			if game_state == GameStates.SHOW_INVENTORY:
				player_turn_results.extend(player.inventory.use(item))
			elif game_state == GameStates.DROP_INVENTORY:
				player_turn_results.extend(player.inventory.drop_item(item))

		if exit:
			if game_state in (GameStates.SHOW_INVENTORY, GameStates.DROP_INVENTORY):
				game_state = previous_game_state
				fov_recompute = True
			else:
				return True


		if fullscreen:
			libtcod.console_set_fullscreen(not libtcod.console_is_fullscreen())
		
		##-----PLAYER TURN RESULTS
		for player_turn_result in player_turn_results:
			message = player_turn_result.get('message')
			dead_entity = player_turn_result.get('dead')
			item_added = player_turn_result.get('item_added')
			item_consumed = player_turn_result.get('consumed')
			item_dropped = player_turn_result.get('item_dropped')

			if message:
				message_log.add_message(message)
			
			if dead_entity:
				if dead_entity == player:
					message, game_state = kill_player(dead_entity)
				else:
					message = kill_monster(dead_entity)
				
				message_log.add_message(message)
			
			if item_added:
				entities.remove(item_added)
				fov_recompute = True
				game_state = GameStates.ENEMY_TURN
			
			if item_consumed:
				game_state = GameStates.ENEMY_TURN
			
			if item_dropped:
				entities.append(item_dropped)
				game_state = GameStates.ENEMY_TURN
		
		if game_state == GameStates.ENEMY_TURN:
			for entity in entities:
				if entity.ai: #if an entity object has an ai, it gets a turn.
					# entity.ai.take_turn(player, fov_map, game_map, entities)
					enemy_turn_results = entity.ai.take_turn(player, fov_map, game_map, entities)

					for enemy_turn_result in enemy_turn_results:
						message = enemy_turn_result.get('message')
						dead_entity = enemy_turn_result.get('dead')

						if message:
							message_log.add_message(message)
							
						if dead_entity:
							if dead_entity == player:
								message, game_state = kill_player(dead_entity)
							else:
								message = kill_monster(dead_entity)
							
							message_log.add_message(message)

							if game_state == GameStates.PLAYER_DEAD:
								break
					if game_state == GameStates.PLAYER_DEAD:
						break
			else:
				#after all the enemies move, players turn
				game_state = GameStates.PLAYERS_TURN

if __name__ == '__main__':
	main()