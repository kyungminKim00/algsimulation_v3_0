from collections import deque

import fire
import gym
import numpy as np
import torch
from torch.distributions import Categorical
from tqdm import tqdm

from base_constants import Memory, device
from ppg import PPG

# from torch import nn
# from torch.utils.data import Dataset, DataLoader
# from torch.optim import Adam
# import torch.nn.functional as F


def exists(val):
    return val is not None


# main
def main(
    env_name="LunarLander-v2",
    num_episodes=50000,
    max_timesteps=500,
    actor_hidden_dim=32,
    critic_hidden_dim=256,
    minibatch_size=64,
    lr=0.0005,
    betas=(0.9, 0.999),
    lam=0.95,
    gamma=0.99,
    eps_clip=0.2,
    value_clip=0.4,
    beta_s=0.01,
    update_timesteps=5000,
    num_policy_updates_per_aux=32,
    epochs=1,
    epochs_aux=6,
    seed=None,
    render=False,
    render_every_eps=250,
    save_every=1000,
    monitor=False,
):
    env = gym.make(env_name)

    if monitor:
        env = gym.wrappers.Monitor(
            env, "./model/phasic_policy_gradient/tmp/", force=True
        )

    state_dim = env.observation_space.shape[0]
    num_actions = env.action_space.n

    memories = deque([])
    aux_memories = deque([])

    agent = PPG(
        state_dim,
        num_actions,
        actor_hidden_dim,
        critic_hidden_dim,
        epochs,
        epochs_aux,
        minibatch_size,
        lr,
        betas,
        lam,
        gamma,
        beta_s,
        eps_clip,
        value_clip,
    )

    if exists(seed):
        torch.manual_seed(seed)
        np.random.seed(seed)

    time = 0
    updated = False
    num_policy_updates = 0

    for eps in tqdm(range(num_episodes), desc="episodes"):
        render_eps = render and eps % render_every_eps == 0
        state = env.reset()
        for _ in range(max_timesteps):
            time += 1

            if updated and render_eps:
                env.render()

            state = torch.from_numpy(state).to(device)
            action_probs, _ = agent.actor(state)
            value = agent.critic(state)

            dist = Categorical(action_probs)
            action = dist.sample()
            action_log_prob = dist.log_prob(action)
            action = action.item()

            next_state, reward, done, _ = env.step(action)

            memory = Memory(state, action, action_log_prob, reward, done, value)
            memories.append(memory)

            state = next_state

            if time % update_timesteps == 0:
                agent.learn(memories, aux_memories, next_state)
                num_policy_updates += 1
                memories.clear()

                if num_policy_updates % num_policy_updates_per_aux == 0:
                    agent.learn_aux(aux_memories)
                    aux_memories.clear()

                updated = True

            if done:
                if render_eps:
                    updated = False
                break

        if render_eps:
            env.close()

        if eps % save_every == 0:
            agent.save()


if __name__ == "__main__":
    fire.Fire(main)
