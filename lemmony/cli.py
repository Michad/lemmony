import requests
import argparse

def main():
    # parse arguments
    parser = argparse.ArgumentParser(description='Subscribe to all new communities on a lemmy instance!')
    parser.add_argument('-i', '--include', nargs='+', help='only include these instances (space separated)')
    parser.add_argument('-e', '--exclude', nargs='+', help='exclude these instances (space separated)')
    parser.add_argument('-l', '--local', help='local instance to subscribe to i.e. lemmy.co.uk', required=True)
    parser.add_argument('-u', '--username', help='username to subscribe with i.e. fed_sub_bot', required=True)
    parser.add_argument('-p', '--password', help='password for user', required=True)
    args = parser.parse_args()

    # define local instance, username, password and include/exclude lists
    local_instance = args.local
    username = args.username
    password = args.password

    if args.include is not None:
        include_instances = args.include
    else:
        include_instances = []

    if args.exclude is not None:
        exclude_instances = args.exclude
    else:
        exclude_instances = []

    # get community and magazine numbers from lemmyverse.net for fetching pagination
    print('fetching lemmy communities and kbin magazines from lemmyverse.net...')
    meta = requests.get('https://lemmyverse.net/data/meta.json')
    communities_total = meta.json()['communities']
    magazines_total = meta.json()['magazines']

    communities_pages = communities_total // 500
    magazines_pages = magazines_total // 500

    # get communities and add to community_actor list
    community_actors = []
    while communities_pages >= 0:
        communities = requests.get('https://lemmyverse.net/data/community/' + str(communities_pages) + '.json')
        for community in communities.json():
            if community['counts']['posts'] > 0 and not community['baseurl'] in exclude_instances and (include_instances == [] or community['baseurl'] in include_instances):
                community_actors.append(community['url'])
        communities_pages -= 1
    community_count = str(len(community_actors))
    print('got ' + community_count + ' non-empty lemmy communities.')

    # get magazines and add to magazine_actor list (lemmyverse api does not show post count, we get them all)
    magazine_actors = []
    while magazines_pages >= 0:
        magazines = requests.get('https://lemmyverse.net/data/magazines/' + str(magazines_pages) + '.json')
        for magazine in magazines.json():
            if not magazine['baseurl'] in exclude_instances and (include_instances == [] or magazine['baseurl'] in include_instances):
                magazine_actors.append(magazine['actor_id'])
        magazines_pages -= 1
    magazine_count = str(len(magazine_actors))
    print('got ' + magazine_count + ' kbin magazines.')

    # merge community and magazine actor lists to all_actor (url) list and count (for displaying progress)
    all_actors = community_actors + magazine_actors
    all_actor_count = str(len(all_actors))

    # create new session object for local instance
    curSession = requests.Session()
    
    # login and get jwt token
    payload='{"username_or_email": "'+username+'","password": "'+password+'"}'
    print('logging in to ' + local_instance + ' as ' + username + '...')
    login_resp = curSession.post('https://'+local_instance+'/api/v3/user/login', data=payload, headers={"Content-Type": "application/json"})
    #print(login_resp.status_code)
    auth_token = login_resp.json()['jwt']

    # get local communities and store id (number) and actor_id (url) in lists
    print('enumerating all local communities (this might take a while)...')
    local_community_id_list = []
    local_community_actor_id_list = []
    new_results = True
    page = 1
    while new_results:
        actor_resp = curSession.get('https://'+local_instance+'/api/v3/community/list?type_=All&limit=50&page=' + str(page), headers={"Cookie": "jwt=" + auth_token})
        if actor_resp.json()['communities'] != []:
            for community in actor_resp.json()['communities']:
                local_community_id_list.append(community['community']['id'])
                local_community_actor_id_list.append(community['community']['actor_id'])
            page += 1
        else:
            new_results = False

    # add remote communities to local communities via. search requests only if they don't already exist
    print('adding new global communities > local instance (this will take a while)...')
    for idx, actor_id in enumerate(all_actors, 1):
        if actor_id not in local_community_actor_id_list:
            actor_resp = curSession.get('https://'+local_instance+'/search?q=' + actor_id + '&type=All&listingType=All&page=1&sort=TopAll', headers={"Cookie": "jwt=" + auth_token})
            print(str(idx) + "/" + all_actor_count + " " + actor_id + ": " + str(actor_resp.status_code))
        else:
            print(str(idx) + "/" + all_actor_count + " " + actor_id + ": already exists")

    # fetch a list of communities by id that the user is not already subscribed to
    print('re-fetching communities ready for subscription (this might take a while)...')
    local_community_id_list = []
    new_results = True
    page = 1
    while new_results:
        actor_resp = curSession.get('https://'+local_instance+'/api/v3/community/list?type_=All&limit=50&page=' + str(page) + '&auth=' + auth_token, headers={"Content-Type": "application/json"})
        if actor_resp.json()['communities'] != []:
            for community in actor_resp.json()['communities']:
                if community['subscribed'] == 'Subscribed':
                    pass
                else:
                    local_community_id_list.append(community['community']['id'])
            page += 1
        else:
            new_results = False

    # store and display total in the list for displaying progress
    local_community_count = str(len(local_community_id_list))
    print('found ' + local_community_count + ' communities to subscribe to.')

    # subscribe the user to all unsubscribed communities
    print('subscribing ' + username + ' to communities (this will take a while)...')
    for idx, community_id in enumerate(local_community_id_list, 1):
        sub_resp = curSession.post('https://'+local_instance+'/api/v3/community/follow', data='{"community_id": ' + str(community_id) + ', "follow": true, "auth": "' + auth_token + '"}', headers={"Cookie": "jwt=" + auth_token, "Content-Type": "application/json"})
        print(str(idx) + "/" + local_community_count + " " + str(community_id) + ": " + str(sub_resp.json()['community_view']['subscribed']))

    # be done
    print('done.')

if __name__ == "__main__":
    main()