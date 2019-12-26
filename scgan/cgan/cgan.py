from typing import Tuple

import numpy as np
from keras import Model, Input
from keras.optimizers import Adam, Optimizer
from keras.utils import generic_utils as keras_generic_utils
from data.generator import SentinelDataGenerator
from util.plotter import Plotter


class CGAN():

    def __init__(self, data_generator: SentinelDataGenerator,
                 discriminative_network_model: Model,
                 generative_network_model: Model,
                 input_shape: Tuple[int, int, int],
                 condition_shape: Tuple[int, int, int],
                 optimizer: Optimizer = Adam(0.0005, 0.5)):
        self.data_generator = data_generator
        self.discriminative_network_model = discriminative_network_model
        self.generative_network_model = generative_network_model
        self.input_shape = input_shape
        self.condition_shape = condition_shape

        input = Input(shape=input_shape)
        condition = Input(shape=condition_shape)
        artificial = self.generative_network_model(condition)
        validatable = self.discriminative_network_model([artificial, condition])

        self.cgan_model = Model(inputs=[input, condition], outputs=[validatable, artificial], name='sentinel-cgan')
        self.cgan_model.compile(loss=['mae', 'mse'], optimizer=optimizer)
        self.plotter = Plotter(generative_network_model, data_generator)

    # TODO accumulate information, early stopping
    def train(self, epochs: int = 5, batch: int = 1, pixel_range: Tuple[int, int] = (0, 1)):

        processed_images_count = len(self.data_generator.images_df())

        for epoch in range(epochs):

            progress_bar = keras_generic_utils.Progbar(processed_images_count)
            epoch_number = epoch + 1
            print('\nepoch %s from %s' % (epoch_number, epochs))

            for i, (satellite_images, mask_images) in enumerate(self.data_generator.load(batch)):
                effective_batch_size = len(satellite_images)

                def form_base(bound):
                    modifier = int(self.input_shape[0] / 2 ** 4)
                    return np.full((effective_batch_size,) + (modifier, modifier, 1), bound)

                artificial_base = form_base(pixel_range[0])
                validatable_base = form_base(pixel_range[1])

                artificial_satellite_image = self.generative_network_model.predict(mask_images)

                real_dn_loss = self.discriminative_network_model.train_on_batch(x=[satellite_images, mask_images],
                                                                                y=validatable_base)

                artificial_dn_loss = self.discriminative_network_model.train_on_batch(
                    x=[artificial_satellite_image, mask_images],
                    y=artificial_base)

                dn_loss = np.add(real_dn_loss, artificial_dn_loss) / 2
                gn_loss = self.cgan_model.train_on_batch(x=[satellite_images, mask_images],
                                                         y=[artificial_base, satellite_images])

                dn_loss_metrics = list(zip(self.discriminative_network_model.metrics_names, dn_loss))
                gn_loss_metrics = list(zip(self.cgan_model.metrics_names, gn_loss))

                progress_bar.add(effective_batch_size, values=dn_loss_metrics + gn_loss_metrics)

            self.plotter.plot(epoch_number)
